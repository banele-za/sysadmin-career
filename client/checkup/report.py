"""The diagnostic report a stuck player can paste to the developer.

Plain text, readable by a human: the checkup results, the raw facts, and
the tail of the logs. The user's home folder is replaced by "~" so their
username doesn't end up in a bug report.
"""

import os
import platform
import subprocess
import time
from pathlib import Path

from client import config, host
from client.checkup.checks import Checkup
from client.checkup.facts import Facts

LOG_LINES = 40


def build(facts: Facts, checkup: Checkup, extra_error: str = "") -> str:
    lines = [
        "Sysadmin Career - diagnostic report",
        f"created: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"game: {_game_version()}",
        f"python: {platform.python_version()}  qemu: {_qemu_version()}",
        "",
        f"mode: {checkup.mode}  vm memory: {checkup.vm_memory_mb} MB  "
        f"warm spare: {checkup.warm_spare}  blocking: {checkup.blocking}",
    ]
    if extra_error:
        lines += ["", f"error: {extra_error}"]
    lines += ["", "== checks"]
    for c in checkup.checks:
        lines.append(f"[{c.status:6}] {c.title}: {c.message}")
    lines += ["", "== facts"]
    for key, value in facts.as_dict().items():
        lines.append(f"{key}: {value}")
    for log in (config.GAME_LOG, config.QEMU_LOG):
        lines += ["", f"== last lines of {log.name}"] + _tail(log)
    return _redact("\n".join(lines) + "\n")


def save_and_copy(text: str) -> str:
    """Write the report to the data folder and put it on the clipboard.

    Returns a sentence for the player saying what happened.
    """
    config.DIAGNOSTIC_REPORT.parent.mkdir(parents=True, exist_ok=True)
    config.DIAGNOSTIC_REPORT.write_text(text, encoding="utf-8")
    where = _redact(str(config.DIAGNOSTIC_REPORT))
    if host.copy_to_clipboard(text):
        return f"Copied to the clipboard (also saved to {where})."
    return f"Saved to {where}."


def _tail(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_LINES:] or ["(empty)"]
    except OSError:
        return ["(missing)"]


def _game_version() -> str:
    if config.VERSION_FILE.exists():                 # packaged game: no git here
        return config.VERSION_FILE.read_text(encoding="utf-8").strip()
    try:
        out = host.run(["git", "-C", str(config.REPO_ROOT), "describe", "--always", "--dirty"],
                       capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _qemu_version() -> str:
    try:
        out = host.run([str(config.qemu_binary("qemu-system-x86_64")), "--version"],
                       capture_output=True, text=True, timeout=10)
        return out.stdout.splitlines()[0] if out.stdout else "unknown"
    except (OSError, subprocess.SubprocessError, FileNotFoundError):
        return "not found"


def _redact(text: str) -> str:
    home = str(Path.home())
    text = text.replace(home, "~").replace(home.replace("\\", "/"), "~")
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if user and len(user) > 2:
        text = text.replace(user, "<user>")
    return text
