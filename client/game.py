"""The game session: ties the checkup, VM, tickets, terminal, mentor and save file together.

Everything here runs on one asyncio event loop. It talks to the UI only
through `emit(event_dict)`, so it doesn't know or care that the UI is a web page.

Events sent to the UI (the "type" field):
  status    {text}                   progress messages while the VM starts or resets
  stats     {xp, rep, mode, tier...} counters and career progress in the top bar
  checkup   {checkup, error, ...}    show the checkup screen (see _show_checkup)
  checkup_notice {text, restart}     result of a fix, shown on the checkup screen
  guide     {brand, steps, ...}      the BIOS guide
  download_progress {done, total}    image download progress, in bytes
  checkup_closed {}                  hide the checkup screen
  ticket    {...}                    a new ticket to show
  term      {data}                   terminal output (base64)
  term_reset {}                      clear the terminal for a new ticket
  mentor    {text, needs_ack}        a mentor chat message
  graded    {passed, checks, ...}    result of pressing Submit
  error     {text}
"""

import asyncio
import base64
import logging
from typing import Callable

import yaml

from client import config
from client.checkup import checks as checks_mod, download, facts as facts_mod, fixes, guides, report
from client.engine import economy, grader, progression, tickets
from client.save.db import SaveFile
from client.ssh.bridge import TerminalBridge
from client.vm import accel
from client.vm.manager import VMManager

log = logging.getLogger(__name__)

TRACK = "rhel"
MENTOR_POLL_SECONDS = {"fast": 2.0, "slow": 5.0}   # slow mode: leave the CPU to the VM


def load_cast() -> dict:
    path = config.CONTENT_DIR / "characters" / "cast.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


class Game:
    def __init__(self, emit: Callable[[dict], None], force_software: bool = False):
        self.emit = emit
        self.force_software = force_software
        self.vm: VMManager | None = None          # created once the checkup has passed
        self.save = SaveFile(config.SAVE_DB, track=TRACK)
        self.tickets = tickets.load_all(config.TICKETS_DIR, track=TRACK)
        self.cast = load_cast()
        self.terminal = TerminalBridge(on_output=self._on_term_output, on_closed=self._on_term_closed)
        self.term_size = (80, 24)

        self.facts: facts_mod.Facts | None = None
        self.checkup: checks_mod.Checkup | None = None
        self._checkup_done: asyncio.Event | None = None   # set when the player may continue

        self.current: tickets.TicketInstance | None = None
        self.attempt_id: int | None = None
        self.solved = False
        self._mentor_task: asyncio.Task | None = None
        self._mentor_ack = asyncio.Event()
        self._busy = asyncio.Lock()      # one reset/grade at a time

    @property
    def mode(self) -> str:
        if self.vm and self.vm.accel:
            return "fast" if self.vm.accel.hardware else "slow"
        return ""

    # ---- called by the UI (via app.py) ------------------------------------

    async def start(self) -> None:
        """Checkup, then VM, then the first ticket.

        If the VM fails to start, show the checkup again with the error
        (the design doc: it runs "whenever something breaks") and retry
        when the player says so. Nobody ends on a dead error screen.
        """
        self._emit_stats()
        error = ""
        while True:
            try:
                await self._checkup_gate(error)
                await self._start_vm()
                break
            except Exception as e:
                self._log_exception(e)
                error = f"{type(e).__name__}: {e}"
                if self.vm:
                    await self.vm.stop()
                    self.vm = None
        self._emit_stats()
        await self.next_ticket()

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

    async def open_checkup(self) -> None:
        """The Settings button / "Try to fix again": run the checkup while playing."""
        await self._run_checkup()
        self._show_checkup(can_close=True)

    async def checkup_action(self, action: str) -> None:
        """A button on the checkup screen or the BIOS guide."""
        try:
            await self._checkup_action(action)
        except Exception as e:
            self._log_exception(e)
            self.emit({"type": "checkup_notice", "text": f"That didn't work: {e}", "restart": False})

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
        if self.vm:
            await self.vm.stop()
        self.save.close()

    # ---- checkup -------------------------------------------------------------

    async def _run_checkup(self) -> None:
        self.emit({"type": "status", "text": "Checking your computer..."})
        self.facts = await asyncio.to_thread(facts_mod.gather)
        self.checkup = checks_mod.evaluate(self.facts)
        log.info("checkup: mode=%s blocking=%s %s", self.checkup.mode, self.checkup.blocking,
                 [(c.key, c.status) for c in self.checkup.checks])

    async def _checkup_gate(self, error: str) -> None:
        """Run the checkup; show its screen only when the player needs to see it."""
        await self._run_checkup()
        first_run = not self.save.get_setting("checkup_seen", False)
        unexplained_slow = (self.checkup.mode == "slow" and not self.force_software
                            and not self.save.get_setting("slow_mode_accepted", False))
        if first_run or error or self.checkup.blocking or unexplained_slow:
            self._checkup_done = asyncio.Event()
            self._show_checkup(error=error, first_run=first_run)
            await self._checkup_done.wait()
            self.emit({"type": "checkup_closed"})
        self.save.set_setting("checkup_seen", True)
        if self.checkup.mode == "fast":
            # Fixed since last time: if fast mode ever breaks again, say so.
            self.save.set_setting("slow_mode_accepted", False)

    def _show_checkup(self, error: str = "", first_run: bool = False, can_close: bool = False) -> None:
        self.emit({
            "type": "checkup",
            "checkup": self.checkup.as_dict(),
            "error": error,
            "first_run": first_run,
            "can_close": can_close,           # opened from Settings while playing
            "running_mode": self.mode,        # what the VM uses right now ("" if not started)
            "fake": self.facts.fake,
        })

    async def _checkup_action(self, action: str) -> None:
        notice = lambda text, restart=False: self.emit(
            {"type": "checkup_notice", "text": text, "restart": restart})

        if action in ("retry", "refresh"):
            await self._run_checkup()
            self._show_checkup(can_close=self._checkup_done is None or self._checkup_done.is_set())
        elif action == "continue":
            if self.checkup and not self.checkup.blocking and self._checkup_done:
                self._checkup_done.set()
        elif action == "slow_mode":
            self.save.set_setting("slow_mode_accepted", True)
            if self._checkup_done and not self.checkup.blocking:
                self._checkup_done.set()
            else:
                self.emit({"type": "checkup_closed"})
        elif action == "close":
            self.emit({"type": "checkup_closed"})
        elif action == "enable_feature":
            result = await asyncio.to_thread(fixes.enable_windows_feature)
            notice(result.message, result.needs_restart)
        elif action == "kvm_fix":
            result = await asyncio.to_thread(fixes.fix_kvm_permissions)
            notice(result.message)
        elif action == "install_qemu":
            self.emit({"type": "checkup_notice", "text": "Installing QEMU...", "restart": False})
            result = await asyncio.to_thread(fixes.install_qemu)
            await self._run_checkup()          # QEMU now found: the red line turns green
            self._show_checkup(can_close=self._checkup_done is None or self._checkup_done.is_set())
            notice(result.message)
        elif action == "restart_now":
            notice((await asyncio.to_thread(fixes.restart_computer)).message)
        elif action == "restart_bios":
            notice((await asyncio.to_thread(fixes.restart_computer, True)).message)
        elif action == "bios_guide":
            self.emit({"type": "guide", **guides.build(self.facts.manufacturer, self.facts.cpu_vendor)})
        elif action == "report":
            text = report.build(self.facts, self.checkup)
            notice(await asyncio.to_thread(report.save_and_copy, text))
        elif action == "download":
            await self._download_image()
        else:
            raise ValueError(f"unknown checkup action {action!r}")

    async def _download_image(self) -> None:
        loop = asyncio.get_running_loop()
        last_percent = -1

        def progress(done: int, total: int) -> None:     # runs on the download thread
            nonlocal last_percent
            percent = done * 100 // max(total, 1)
            if percent != last_percent:
                last_percent = percent
                loop.call_soon_threadsafe(self.emit, {"type": "download_progress",
                                                      "done": done, "total": total})

        try:
            await asyncio.to_thread(download.download_all, config.IMAGE_RELEASE_URL,
                                    config.IMAGES_DIR, progress)
        except (download.DownloadError, OSError, ValueError) as e:
            self._log_exception(e)
            self.emit({"type": "checkup_notice", "text": f"The download didn't finish: {e}",
                       "restart": False})
        await self._run_checkup()
        self._show_checkup()

    async def _start_vm(self) -> None:
        c = self.checkup
        if self.force_software or c.mode == "slow":
            chosen = accel.SOFTWARE
        else:
            chosen = accel.hardware_candidate()
        self.vm = VMManager(
            on_status=lambda text: self.emit({"type": "status", "text": text}),
            accel=chosen,
            memory_mb=c.vm_memory_mb,
            warm_spare=c.warm_spare and chosen.hardware,
        )
        await self.vm.start()

    # ---- ticket flow -------------------------------------------------------

    def _pick_ticket(self) -> tickets.Ticket:
        """Next ticket on the career ladder (see engine/progression.py)."""
        current_id = self.current.ticket.id if self.current else None
        return progression.pick_next(self.tickets, self.save.solved_ticket_ids(), current_id)

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
        elif ticket.mentor_intro:
            # Unguided, but the mentor introduces the idea first (no commands).
            self.emit({"type": "mentor", "text": instance.text(ticket.mentor_intro).strip(),
                       "needs_ack": False})

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
        poll = MENTOR_POLL_SECONDS.get(self.mode, 2.0)
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
                    await asyncio.sleep(poll)
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
        prog = progression.progress(self.tickets, self.save.solved_ticket_ids())
        self.emit({"type": "stats", "xp": p.xp, "rep": p.rep, "mode": self.mode or None,
                   "tier": prog.tier_name, "tier_solved": prog.solved, "tier_total": prog.total})

    def _log_exception(self, e: Exception) -> None:
        log.error("%s: %s", type(e).__name__, e, exc_info=e)

    def _report(self, e: Exception) -> None:
        self._log_exception(e)
        self.emit({"type": "error", "text": f"{type(e).__name__}: {e}"})
