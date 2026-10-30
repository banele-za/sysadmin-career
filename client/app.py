"""Game entry point: opens the window and runs the game.

Run from the repo root:
    .venv\\Scripts\\python -m client.app            (Windows; add --software to force slow mode)
    .venv/bin/python -m client.app                (Linux)

Threads:
  main thread    - pywebview's window (GUI toolkits insist on the main thread)
  game thread    - an asyncio event loop running client.game.Game
  emit thread    - delivers events to the web page in order

JavaScript calls methods on `Api` (window.pywebview.api.*); those hand the
work to the game thread. The game calls `emit`, which queues an event that
the emit thread pushes into the page with evaluate_js.
"""

import argparse
import asyncio
import json
import logging
import queue
import sys
import threading

import webview

from client import config, host
from client.game import Game


class Api:
    """Methods the web page can call. Each runs on a pywebview worker thread."""

    def __init__(self, loop: asyncio.AbstractEventLoop, game: Game):
        self._loop = loop
        self._game = game

    def _spawn(self, coro) -> None:
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _call(self, fn, *args) -> None:
        self._loop.call_soon_threadsafe(fn, *args)

    # Names here become window.pywebview.api.<name> in JavaScript.
    def ready(self):
        self._spawn(self._game.start())

    def submit(self):
        self._spawn(self._game.submit())

    def next_ticket(self):
        self._spawn(self._game.next_ticket())

    def open_checkup(self):
        self._spawn(self._game.open_checkup())

    def checkup_action(self, action):
        self._spawn(self._game.checkup_action(str(action)))

    def mentor_ack(self):
        self._call(self._game.mentor_ack)

    def term_input(self, data):
        self._call(self._game.term_input, data)

    def term_resize(self, cols, rows):
        self._call(self._game.term_resize, int(cols), int(rows))


class Emitter:
    """Push events into the page from one thread, so they arrive in order."""

    def __init__(self):
        self.window: webview.Window | None = None
        self._queue: queue.Queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True, name="emit").start()

    def __call__(self, event: dict) -> None:
        self._queue.put(event)

    def _run(self) -> None:
        while True:
            event = self._queue.get()
            if self.window is None:
                continue
            try:
                self.window.evaluate_js(f"window.game.onEvent({json.dumps(event)})")
            except Exception as e:      # window closing, page not loaded yet, ...
                logging.getLogger(__name__).warning("emit failed: %s", e)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--software", action="store_true", help="force slow (software) mode")
    parser.add_argument("--debug", action="store_true", help="enable the web inspector")
    args = parser.parse_args()
    _setup_logging()

    loop = asyncio.new_event_loop()
    game_thread = threading.Thread(target=loop.run_forever, daemon=True, name="game")
    game_thread.start()

    emitter = Emitter()
    # Game() must be created on the game thread: it makes asyncio objects.
    game = asyncio.run_coroutine_threadsafe(_make_game(emitter, args.software), loop).result()

    width, height, x, y = _window_geometry()
    window = webview.create_window(
        "Sysadmin Career", url=str(config.UI_DIR / "index.html"),
        js_api=Api(loop, game), width=width, height=height, x=x, y=y, min_size=(960, 600),
        background_color="#14161a",
    )
    emitter.window = window
    # icon: used on Linux only (on Windows the .exe's own icon is shown).
    webview.start(gui=host.WEBVIEW_GUI, debug=args.debug, icon=str(config.ICON))

    # The window was closed: shut the VM down cleanly before exiting.
    logging.getLogger(__name__).info("window closed, shutting down VM")
    asyncio.run_coroutine_threadsafe(game.shutdown(), loop).result(timeout=30)
    loop.call_soon_threadsafe(loop.stop)


def _setup_logging() -> None:
    """Log to the console and to game.log (the diagnostic report includes its tail)."""
    config.GAME_LOG.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(config.GAME_LOG, mode="w", encoding="utf-8")]
    if sys.stderr:      # the packaged game has no console, and then sys.stderr is None
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers)
    logging.getLogger("asyncssh").setLevel(logging.WARNING)    # very chatty at INFO


def _window_geometry() -> tuple[int, int, int | None, int | None]:
    """(width, height, x, y): up to 1400x860, centered in the usable screen area.

    "Usable" means without the taskbar: pywebview's default spot can leave
    the bottom of a large window hidden behind it.

    Only Windows tells us the usable area before the window exists. On Linux
    we pick a size that fits a 1366x768 laptop and let the desktop's window
    manager place it (x, y = None). (pywebview's screen list isn't ready
    before Qt starts, and guessing placed the window half off-screen.)
    """
    area = host.work_area()
    if area is None:
        return 1280, 720, None, None
    left, top, width, height = area
    w, h = min(1400, int(width * 0.92)), min(860, int(height * 0.92))
    return w, h, left + (width - w) // 2, top + (height - h) // 2


async def _make_game(emit, force_software: bool) -> Game:
    return Game(emit, force_software=force_software)


if __name__ == "__main__":
    main()
