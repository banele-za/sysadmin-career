"""Play through both tickets like a player would, without the window.

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


def test_play_both_tickets(sandbox):
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
        await game.start()

        # --- Ticket 1: the guided tutorial --------------------------------
        ticket = ui.of_type("ticket")[-1]
        assert ticket["id"] == "tut-01-files" and ticket["guided"]
        await ui.wait_for(lambda: "admin@srv01" in ui.screen, 30, "shell prompt")

        await ui.wait_for(lambda: ui.of_type("mentor"), 10, "first mentor message")
        assert ui.of_type("mentor")[0]["needs_ack"]
        game.mentor_ack()                                 # the "Got it" button

        codeword = game.current.values["codeword"]
        for cmd in ["pwd", "mkdir notes", "cd onboarding", "cp welcome.txt ../notes/",
                    f"mv ../notes/welcome.txt ../notes/{codeword}.txt",
                    "rm DELETE-ME.tmp", "touch ../notes/done"]:
            await _type(game, ui, cmd)

        # The mentor follows along and finishes all 5 checked steps.
        await ui.wait_for(lambda: len(ui.of_type("mentor_step_done")) == 5, 30, "mentor steps")

        await game.submit()
        graded = ui.of_type("graded")[-1]
        assert graded["passed"], graded["checks"]
        assert (graded["xp"], graded["rep"]) == (20, 5)

        # --- Ticket 2: Gary's shared folder (unguided) ----------------------
        await game.next_ticket()
        ticket = ui.of_type("ticket")[-1]
        assert ticket["id"] == "perm-03-setgid-shared" and not ticket["guided"]
        await ui.wait_for(lambda: ui.screen.count("admin@srv01") >= 2, 30, "new shell")

        v = game.current.values
        # A wrong answer first: Gary's style. Grading must say what's wrong.
        await _type(game, ui, f"sudo chmod 777 {v['dir']}")
        await game.submit()
        graded = ui.of_type("graded")[-1]
        assert not graded["passed"]
        assert any(not c["pass"] for c in graded["checks"])

        # Now the real fix, typed as the player.
        await _type(game, ui, f"sudo chgrp -R {v['group']} {v['dir']}")
        await _type(game, ui, f"sudo chmod 2770 {v['dir']}")
        await _type(game, ui, f"sudo sh -c 'chmod g+w {v['dir']}/*'")
        for user in v["users"]:
            await _type(game, ui, f"echo 'umask 002' | sudo tee -a /home/{user}/.bashrc")
        await game.submit()
        graded = ui.of_type("graded")[-1]
        assert graded["passed"], graded["checks"]

        stats = ui.of_type("stats")[-1]
        assert (stats["xp"], stats["rep"]) == (60, 20)
        assert game.save.player().xp == 60              # persisted to SQLite
    finally:
        await game.shutdown()
