"""Climb the whole ticket ladder like a player would, without the window.

Drives client.game.Game directly: types commands into the real terminal
session, follows the mentor, presses Submit, and checks XP and reputation.

    .venv\\Scripts\\python -m pytest tests\\test_game.py -s
"""

import asyncio
import base64

import pytest

from client import config
from client.game import Game

pytestmark = pytest.mark.skipif(not config.BASE_IMAGE.exists(), reason="base image not built")


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    folder = config.REPO_ROOT / "data" / "test-vm"
    monkeypatch.setattr(config, "OVERLAY_DISK", folder / "overlay.qcow2")
    monkeypatch.setattr(config, "SERIAL_LOG", folder / "serial.log")
    monkeypatch.setattr(config, "QEMU_LOG", folder / "qemu.log")
    monkeypatch.setattr(config, "SAVE_DB", tmp_path / "save.db")


def test_play_the_ladder(sandbox):
    asyncio.run(_play())


class Recorder:
    """Collects the events the game sends to the UI."""

    def __init__(self):
        self.events: list[dict] = []
        self.screen = ""          # all terminal output so far, decoded

    def __call__(self, event: dict) -> None:
        self.events.append(event)
        if event["type"] == "term":
            self.screen += base64.b64decode(event["data"]).decode(errors="replace")
        if event["type"] == "error":
            raise AssertionError(event["text"])

    def of_type(self, kind: str) -> list[dict]:
        return [e for e in self.events if e["type"] == kind]

    async def wait_for(self, predicate, timeout: float = 60, what: str = "condition"):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not predicate():
            if loop.time() > deadline:
                raise TimeoutError(f"timed out waiting for {what}\nscreen tail:\n{self.screen[-500:]}")
            await asyncio.sleep(0.2)


async def _type(game: Game, ui: Recorder, line: str) -> None:
    """Type a command, press Enter, and wait for the next prompt."""
    prompts = ui.screen.count("$ ")
    game.term_input(line + "\r")
    await ui.wait_for(lambda: ui.screen.count("$ ") > prompts, 30, f"prompt after {line!r}")


async def _play():
    ui = Recorder()
    game = Game(ui)
    try:
        # A brand-new save shows the first-run checkup; press "Start playing".
        starting = asyncio.create_task(game.start())
        await ui.wait_for(lambda: ui.of_type("checkup"), 60, "checkup screen")
        assert ui.of_type("checkup")[0]["first_run"]
        await game.checkup_action("continue")
        await starting
        assert ui.of_type("story")[0]["kind"] == "intro"     # first day, while the VM booted
        await _tutorial_files(game, ui)
        await _next(game, ui, "tut-02-perms", guided=True)
        await _tutorial_perms(game, ui)
        await _next(game, ui, "perm-01-chmod")
        await _chmod(game, ui)
        await _next(game, ui, "perm-02-owner")
        await _owner(game, ui)
        await _next(game, ui, "perm-03-setgid-shared")
        await _setgid(game, ui)

        stats = ui.of_type("stats")[-1]
        total_xp, total_rep = 20 + 20 + 30 + 30 + 40, 5 + 5 + 6 + 10 + 15
        assert (stats["xp"], stats["rep"]) == (total_xp, total_rep)
        assert game.save.player().xp == total_xp           # persisted to SQLite
        assert stats["tier"] == "Sysadmin"                 # Tier 1 done
        assert [s["kind"] for s in ui.of_type("story")] == ["intro", "promotion"]
    finally:
        await game.shutdown()


async def _next(game: Game, ui: Recorder, ticket_id: str, guided: bool = False):
    """Press "Next ticket" and check the ladder handed us the expected one."""
    shells = ui.screen.count("admin@srv01")
    await game.next_ticket()
    ticket = ui.of_type("ticket")[-1]
    assert (ticket["id"], ticket["guided"]) == (ticket_id, guided)
    await ui.wait_for(lambda: ui.screen.count("admin@srv01") > shells, 30, "new shell")


async def _submit_passes(game: Game, ui: Recorder, xp: int, rep: int):
    await game.submit()
    graded = ui.of_type("graded")[-1]
    assert graded["passed"], graded["checks"]
    assert (graded["xp"], graded["rep"]) == (xp, rep)


async def _follow_mentor(game: Game, ui: Recorder, commands: list[str], checked_steps: int):
    """Acknowledge the first message, type the commands, wait for the mentor."""
    done_before = len(ui.of_type("mentor_step_done"))
    await ui.wait_for(lambda: ui.of_type("mentor") and ui.of_type("mentor")[-1]["needs_ack"],
                      10, "first mentor message")
    game.mentor_ack()                                    # the "Got it" button
    for cmd in commands:
        await _type(game, ui, cmd)
    await ui.wait_for(lambda: len(ui.of_type("mentor_step_done")) - done_before == checked_steps,
                      30, "mentor steps")


async def _tutorial_files(game: Game, ui: Recorder):
    ticket = ui.of_type("ticket")[-1]
    assert ticket["id"] == "tut-01-files" and ticket["guided"]
    assert ticket["hints_total"] == 0                    # tutorials have the mentor instead
    assert ui.of_type("stats")[-1]["tier"] == "Help Desk"
    await ui.wait_for(lambda: "admin@srv01" in ui.screen, 30, "shell prompt")
    codeword = game.current.values["codeword"]
    await _follow_mentor(game, ui, [
        "pwd", "mkdir notes", "cd onboarding", "cp welcome.txt ../notes/",
        f"mv ../notes/welcome.txt ../notes/{codeword}.txt",
        "rm DELETE-ME.tmp", "touch ../notes/done",
    ], checked_steps=5)
    await _submit_passes(game, ui, 20, 5)


async def _tutorial_perms(game: Game, ui: Recorder):
    v = game.current.values
    await _follow_mentor(game, ui, [
        "cd lesson", "ls -l", f"chmod u+x {v['script']}", f"./{v['script']}",
        f"chmod 600 {v['secret']}",
        f"sudo chown admin {v['handover']}/report.txt",
        f"sudo chgrp {v['group']} {v['handover']}/report.txt",
    ], checked_steps=4)
    await _submit_passes(game, ui, 20, 5)


async def _chmod(game: Game, ui: Recorder):
    v = game.current.values
    # One hint (paid from this ticket's rep: 8 -> 6), then the manual (+5 XP).
    assert ui.of_type("ticket")[-1]["hints_total"] == 3
    game.hint()
    hint = ui.of_type("hint")[-1]
    assert hint["level"] == 1 and "ls -l" in hint["text"] and hint["reward_now"] == 6
    await _type(game, ui, "man chmod | head -3")
    # A wrong answer first, Gary's style. Grading must say what's wrong.
    await _type(game, ui, f"sudo chmod 777 {v['dir']}/{v['report']} {v['dir']}/{v['script']}")
    await game.submit()
    graded = ui.of_type("graded")[-1]
    assert not graded["passed"]
    assert any(not c["pass"] for c in graded["checks"])
    # The real fix, in letters this time (the solution uses numbers).
    await _type(game, ui, f"sudo chmod u=rw,g=r,o= {v['dir']}/{v['report']}")
    await _type(game, ui, f"sudo chmod u+x,g-w {v['dir']}/{v['script']}")
    await _submit_passes(game, ui, 25 + 5, 6)
    assert ui.of_type("graded")[-1]["man_bonus"] == 5


async def _owner(game: Game, ui: Recorder):
    v = game.current.values
    await _type(game, ui, f"sudo chown -R {v['newowner']}:{v['team']} {v['dir']}")
    await _submit_passes(game, ui, 30, 10)


async def _setgid(game: Game, ui: Recorder):
    # Unguided, but the mentor introduces setgid and umask first.
    assert "setgid" in ui.of_type("mentor")[-1]["text"]
    v = game.current.values
    await _type(game, ui, f"sudo chgrp -R {v['group']} {v['dir']}")
    await _type(game, ui, f"sudo chmod 2770 {v['dir']}")
    await _type(game, ui, f"sudo sh -c 'chmod g+w {v['dir']}/*'")
    for user in v["users"]:
        await _type(game, ui, f"echo 'umask 002' | sudo tee -a /home/{user}/.bashrc")
    await _submit_passes(game, ui, 40, 15)
