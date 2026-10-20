"""Game entry point: opens the window and runs the game.

Run from the repo root:
    .venv\\Scripts\\python -m client.app            (add --software to force slow mode)

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
import queue
import threading

import webview

from client import config
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
                print(f"emit failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--software", action="store_true", help="force slow (software) mode")
    parser.add_argument("--debug", action="store_true", help="enable the web inspector")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    game_thread = threading.Thread(target=loop.run_forever, daemon=True, name="game")
    game_thread.start()

    emitter = Emitter()
    # Game() must be created on the game thread: it makes asyncio objects.
    game = asyncio.run_coroutine_threadsafe(_make_game(emitter, args.software), loop).result()

    width, height = _window_size()
    window = webview.create_window(
        "Sysadmin Career", url=str(config.UI_DIR / "index.html"),
        js_api=Api(loop, game), width=width, height=height, min_size=(960, 600),
        background_color="#14161a",
    )
    emitter.window = window
    webview.start(debug=args.debug)

    # The window was closed: shut the VM down cleanly before exiting.
    print("Shutting down VM...")
    asyncio.run_coroutine_threadsafe(game.shutdown(), loop).result(timeout=30)
    loop.call_soon_threadsafe(loop.stop)


def _window_size() -> tuple[int, int]:
    """1400x860, shrunk to 90% of the screen on smaller displays."""
    try:
        screen = webview.screens[0]
        return min(1400, int(screen.width * 0.9)), min(860, int(screen.height * 0.9))
    except (IndexError, AttributeError):
        return 1280, 760


async def _make_game(emit, force_software: bool) -> Game:
    return Game(emit, force_software=force_software)


if __name__ == "__main__":
    main()
