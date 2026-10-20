"""The game session: ties the VM, tickets, terminal, mentor and save file together.

Everything here runs on one asyncio event loop. It talks to the UI only
through `emit(event_dict)`, so it doesn't know or care that the UI is a web page.

Events sent to the UI (the "type" field):
  status    {text}                   progress messages while the VM starts or resets
  stats     {xp, rep, mode}          counters in the top bar
  ticket    {...}                    a new ticket to show
  term      {data}                   terminal output (base64)
  term_reset {}                      clear the terminal for a new ticket
  mentor    {text, needs_ack}        a mentor chat message
  graded    {passed, checks, ...}    result of pressing Submit
  error     {text}
"""

import asyncio
import base64
import traceback
from typing import Callable

import yaml

from client import config
from client.engine import economy, grader, tickets
from client.save.db import SaveFile
from client.ssh.bridge import TerminalBridge
from client.vm.manager import VMManager

TRACK = "rhel"
MENTOR_POLL_SECONDS = 2.0


def load_cast() -> dict:
    path = config.CONTENT_DIR / "characters" / "cast.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


class Game:
    def __init__(self, emit: Callable[[dict], None], force_software: bool = False):
        self.emit = emit
        self.vm = VMManager(on_status=lambda text: emit({"type": "status", "text": text}),
                            force_software=force_software)
        self.save = SaveFile(config.SAVE_DB, track=TRACK)
        self.tickets = tickets.load_all(config.TICKETS_DIR, track=TRACK)
        self.cast = load_cast()
        self.terminal = TerminalBridge(on_output=self._on_term_output, on_closed=self._on_term_closed)
        self.term_size = (80, 24)

        self.current: tickets.TicketInstance | None = None
        self.attempt_id: int | None = None
        self.solved = False
        self._mentor_task: asyncio.Task | None = None
        self._mentor_ack = asyncio.Event()
        self._busy = asyncio.Lock()      # one reset/grade at a time

    # ---- called by the UI (via app.py) ------------------------------------

    async def start(self) -> None:
        try:
            self._emit_stats()
            await self.vm.start()
            self._emit_stats()
            await self.next_ticket()
        except Exception as e:
            self._report(e)

    async def next_ticket(self) -> None:
        async with self._busy:
            try:
                await self._begin(self._pick_ticket())
            except Exception as e:
                self._report(e)

    async def submit(self) -> None:
        if self.current is None or self.solved or self._busy.locked():
            self.emit({"type": "submit_ignored"})   # lets the UI re-enable the button
            return
        async with self._busy:
            try:
                await self._grade()
            except Exception as e:
                self._report(e)

    def mentor_ack(self) -> None:
        self._mentor_ack.set()

    def term_input(self, data: str) -> None:
        self.terminal.write(data)

    def term_resize(self, cols: int, rows: int) -> None:
        self.term_size = (cols, rows)
        self.terminal.resize(cols, rows)

    async def shutdown(self) -> None:
        self._stop_mentor()
        await self.terminal.close()
        await self.vm.stop()
        self.save.close()

    # ---- ticket flow -------------------------------------------------------

    def _pick_ticket(self) -> tickets.Ticket:
        """First unsolved ticket in order; once all are solved, the oldest repeat."""
        solved = self.save.solved_ticket_ids()
        for t in self.tickets:
            if t.id not in solved:
                return t
        # Everything solved: rotate so the same ticket doesn't come up twice in a row.
        if self.current:
            ids = [t.id for t in self.tickets]
            return self.tickets[(ids.index(self.current.ticket.id) + 1) % len(self.tickets)]
        return self.tickets[0]

    async def _begin(self, ticket: tickets.Ticket) -> None:
        self._stop_mentor()
        await self.terminal.close()
        self.emit({"type": "status", "text": "Preparing your next ticket..."})

        # 1. Fresh system.  2. Roll params.  3. Break it.
        await self.vm.reset()
        instance = tickets.instantiate(ticket)
        await grader.run_break(await self.vm.root(), instance, TRACK)

        self.current, self.solved = instance, False
        self.attempt_id = self.save.start_attempt(ticket.id, instance.seed, instance.values)
        character = self.cast.get(ticket.character, {})
        self.emit({
            "type": "ticket",
            "id": ticket.id,
            "title": instance.text(ticket.title),
            "from": character.get("name", ticket.character),
            "role": character.get("role", ""),
            "narrative": instance.narrative,
            "guided": ticket.guided,
            "rewards": ticket.rewards,
        })

        # 4. Hand the terminal to the player.
        self.emit({"type": "term_reset"})
        cols, rows = self.term_size
        await self.terminal.open(self.vm.ssh_port, config.PLAYER_USER, config.PLAYER_KEY, cols, rows)
        self.emit({"type": "status", "text": ""})

        if ticket.guided:
            self._mentor_task = asyncio.create_task(self._run_mentor(instance))

    async def _grade(self) -> None:
        self.emit({"type": "status", "text": "Checking your work..."})
        result = await grader.run_grade(await self.vm.root(), self.current, TRACK)
        self.save.record_submit(self.attempt_id)
        event = {
            "type": "graded",
            "passed": result.passed,
            "checks": [{"name": c.name, "pass": c.passed, "msg": c.msg} for c in result.checks],
        }
        if result.passed:
            already = self.current.ticket.id in self.save.solved_ticket_ids()
            xp, rep = economy.reward_for(self.current.ticket, already)
            self.save.solve(self.attempt_id, xp, rep)
            self.solved = True
            self._stop_mentor()
            event.update(xp=xp, rep=rep)
        self.emit(event)
        self.emit({"type": "status", "text": ""})
        self._emit_stats()

    # ---- mentor ------------------------------------------------------------

    async def _run_mentor(self, instance: tickets.TicketInstance) -> None:
        """Show each step; wait for its check to pass (or for 'Got it')."""
        try:
            conn = await self.vm.root()
            for step in instance.ticket.mentor_steps:
                self.emit({"type": "mentor", "text": instance.text(step.say).strip(),
                           "needs_ack": step.check is None})
                if step.check is None:
                    self._mentor_ack.clear()
                    await self._mentor_ack.wait()
                    continue
                while not await grader.mentor_check(conn, instance, step.check):
                    await asyncio.sleep(MENTOR_POLL_SECONDS)
                self.emit({"type": "mentor_step_done"})
            self.emit({"type": "mentor", "text": "That's everything. Press Submit when you're ready!",
                       "needs_ack": False})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._report(e)

    def _stop_mentor(self) -> None:
        if self._mentor_task:
            self._mentor_task.cancel()
            self._mentor_task = None

    # ---- helpers -----------------------------------------------------------

    def _on_term_output(self, data: bytes) -> None:
        self.emit({"type": "term", "data": base64.b64encode(data).decode()})

    def _on_term_closed(self) -> None:
        # The player typed `exit`. Give them a new shell instead of a dead terminal.
        self.emit({"type": "term", "data": base64.b64encode(
            b"\r\n[session closed - reconnecting]\r\n").decode()})
        asyncio.get_running_loop().create_task(self._reopen_terminal())

    async def _reopen_terminal(self) -> None:
        await self.terminal.close()
        cols, rows = self.term_size
        await self.terminal.open(self.vm.ssh_port, config.PLAYER_USER, config.PLAYER_KEY, cols, rows)

    def _emit_stats(self) -> None:
        p = self.save.player()
        mode = None
        if self.vm.accel:
            mode = "fast" if self.vm.accel.hardware else "slow"
        self.emit({"type": "stats", "xp": p.xp, "rep": p.rep, "mode": mode})

    def _report(self, e: Exception) -> None:
        traceback.print_exc()
        self.emit({"type": "error", "text": f"{type(e).__name__}: {e}"})
