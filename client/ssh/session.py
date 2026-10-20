"""SSH connections to the game VM, and running scripts on it as root."""

import asyncio
import shlex
from dataclasses import dataclass
from pathlib import Path

import asyncssh


async def connect(port: int, user: str, key: Path) -> asyncssh.SSHClientConnection:
    """Open an SSH connection to the VM through the forwarded localhost port.

    known_hosts=None skips host-key checking. That's acceptable only because
    the VM is ours and reachable on 127.0.0.1 alone.
    """
    return await asyncssh.connect(
        "127.0.0.1", port,
        username=user,
        client_keys=[str(key)],
        known_hosts=None,
        connect_timeout=10,
    )


async def wait_until_up(port: int, user: str, key: Path, timeout: float) -> asyncssh.SSHClientConnection:
    """Keep trying to connect until sshd in the VM answers (i.e. it has booted)."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        try:
            return await connect(port, user, key)
        except (OSError, asyncssh.Error, asyncio.TimeoutError):
            # QEMU accepts the TCP connection even before the guest's sshd is
            # listening, then drops it, so "connection lost" just means "not yet".
            if loop.time() > deadline:
                raise TimeoutError(f"VM did not answer SSH within {timeout:.0f}s")
            await asyncio.sleep(1)


@dataclass
class ScriptResult:
    exit_status: int
    stdout: str
    stderr: str


async def run_script(conn: asyncssh.SSHClientConnection, script: str,
                     env: dict[str, str] | None = None, timeout: float = 120) -> ScriptResult:
    """Run a Bash script on the VM, with `env` exported as environment variables.

    sshd only forwards a few environment variables, so instead of sending
    them over SSH we put safely quoted `export` lines at the top of the script.
    """
    exports = "".join(f"export {name}={shlex.quote(value)}\n" for name, value in (env or {}).items())
    result = await conn.run("bash -s", input=exports + script, timeout=timeout)
    # exit_status is None if the script was killed by a signal: treat as failure.
    status = result.exit_status if result.exit_status is not None else -1
    return ScriptResult(status, result.stdout or "", result.stderr or "")
