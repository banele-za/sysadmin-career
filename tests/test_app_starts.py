"""The real game window starts and stays up (catches crashes in client/app.py).

Unit tests drive client.game directly and never open a window, so a bug in
the window code itself (like a wrong icon argument) slipped past them once.
This starts `python -m client.app` with a scratch save, waits until the
game has run its checkup, and checks the process is still alive.
"""

import os
import subprocess
import sys
import time

import pytest

from client import host

pytestmark = pytest.mark.skipif(not host.WINDOWS and not os.environ.get("DISPLAY"),
                                reason="needs a screen (Windows, or Linux with DISPLAY)")


def test_window_starts_and_runs_the_checkup(tmp_path):
    env = {**os.environ, "SYSADMIN_GAME_DATA": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "-m", "client.app"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **host.NO_WINDOW)
    log = tmp_path / "game.log"
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert proc.poll() is None, f"the game exited: {proc.stderr.read().decode(errors='replace')[-2000:]}"
            if log.exists() and "checkup:" in log.read_text(encoding="utf-8", errors="replace"):
                break
            time.sleep(0.5)
        else:
            pytest.fail("the game never reached its checkup")
        time.sleep(2)
        assert proc.poll() is None, "the game exited right after its checkup"
    finally:
        proc.kill()
        proc.wait()
