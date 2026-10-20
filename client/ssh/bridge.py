"""Connect the xterm.js terminal in the window to a real shell on the VM.

    keystrokes:  xterm.js --(js_api)--> write() --> SSH stdin  --> bash on VM
    output:      bash --> SSH stdout --> _pump() --> batched --> on_output --> xterm.js

Output is collected for a few milliseconds and sent in one batch, because
each push into the web page costs far more than the bytes themselves.
Bytes stay bytes (no decoding here): xterm.js decodes UTF-8 itself and
copes with a character split across two batches.
"""

import asyncio
from pathlib import Path
from typing import Callable

import asyncssh

from client.ssh import session

FLUSH_INTERVAL = 0.016    # about one screen refresh


class TerminalBridge:
    def __init__(self, on_output: Callable[[bytes], None], on_closed: Callable[[], None]):
        self.on_output = on_output
        self.on_closed = on_closed
        self._conn: asyncssh.SSHClientConnection | None = None
        self._proc: asyncssh.SSHClientProcess | None = None
        self._tasks: list[asyncio.Task] = []
        self._buffer = bytearray()

    async def open(self, port: int, user: str, key: Path, cols: int, rows: int) -> None:
        self._conn = await session.connect(port, user, key)
        # Asking for a terminal (term_type) gives the player an interactive
        # login shell with a prompt, colours and job control, like a real SSH login.
        self._proc = await self._conn.create_process(
            term_type="xterm-256color", term_size=(cols, rows), encoding=None)
        self._tasks = [asyncio.create_task(self._pump()), asyncio.create_task(self._flush_loop())]

    def write(self, data: str) -> None:
        if self._proc:
            self._proc.stdin.write(data.encode())

    def resize(self, cols: int, rows: int) -> None:
        if self._proc:
            self._proc.change_terminal_size(cols, rows)

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        if self._conn:
            self._conn.close()
        self._conn = self._proc = None
        self._buffer.clear()

    async def _pump(self) -> None:
        try:
            while chunk := await self._proc.stdout.read(65536):
                self._buffer += chunk
        except (asyncssh.Error, OSError):
            pass
        self._flush()
        self.on_closed()      # the shell ended (player typed `exit`) or the link dropped

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(FLUSH_INTERVAL)
            self._flush()

    def _flush(self) -> None:
        if self._buffer:
            data, self._buffer = bytes(self._buffer), bytearray()
            self.on_output(data)
