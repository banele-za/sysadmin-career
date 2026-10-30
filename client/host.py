"""Everything that differs between Windows and Linux, in one place.

In VM terms the player's computer is the "host" and the game's Linux VM is
the "guest". This module is about the host: where files go, how to run a
program without a console window popping up, the clipboard, restarting,
and so on. The rest of the game calls these functions and never checks
sys.platform itself.

Supported hosts: Windows and Linux. (macOS is out of scope for now.)
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"
LINUX = sys.platform.startswith("linux")


# ---- files -------------------------------------------------------------------

def data_dir() -> Path:
    """Per-user folder for the save file, the VM's disks and the image.

    Windows: %LOCALAPPDATA%\\SysadminGame
    Linux:   $XDG_DATA_HOME/sysadmin-game (usually ~/.local/share/sysadmin-game)
    """
    override = os.environ.get("SYSADMIN_GAME_DATA")
    if override:
        return Path(override)
    if WINDOWS and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "SysadminGame"
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "sysadmin-game"


def exe_name(name: str) -> str:
    """'qemu-img' -> 'qemu-img.exe' on Windows."""
    return f"{name}.exe" if WINDOWS else name


# ---- running other programs --------------------------------------------------

# A windowed (no-console) Windows app that starts a console program makes a
# black console window flash up. CREATE_NO_WINDOW prevents that.
NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run without a console window flashing up on Windows."""
    return subprocess.run(cmd, **NO_WINDOW, **kwargs)


# ---- clipboard ---------------------------------------------------------------

def copy_to_clipboard(text: str) -> bool:
    """Put text on the clipboard. False if this computer has no way to."""
    if WINDOWS:
        # clip.exe reads UTF-16 with a byte-order mark as Unicode text.
        commands = [(["clip"], text.encode("utf-16"))]
    else:
        # Wayland desktops have wl-copy, X11 desktops xclip or xsel; any one will do.
        data = text.encode("utf-8")
        commands = [(["wl-copy"], data),
                    (["xclip", "-selection", "clipboard"], data),
                    (["xsel", "--clipboard", "--input"], data)]
    for cmd, data in commands:
        if not shutil.which(cmd[0]):
            continue
        try:
            run(cmd, input=data, check=True, timeout=10)
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


# ---- restarting --------------------------------------------------------------

def restart_command(into_firmware: bool) -> list[str]:
    """The command that restarts this computer in 5 seconds (Windows) or now (Linux).

    into_firmware restarts straight into the BIOS/UEFI setup screen. Both
    systems can only do that on UEFI computers; older ones refuse.
    """
    if WINDOWS:
        return ["shutdown", "/r", "/t", "5"] + (["/fw"] if into_firmware else [])
    # systemd's reboot works for the logged-in desktop user without a password.
    return ["systemctl", "reboot"] + (["--firmware-setup"] if into_firmware else [])


# ---- the screen --------------------------------------------------------------

def work_area() -> tuple[int, int, int, int] | None:
    """(left, top, width, height) of the main screen minus the taskbar, if known.

    Only Windows tells us cheaply; elsewhere the caller uses the whole screen.
    """
    if not WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes
    rect = wintypes.RECT()
    SPI_GETWORKAREA = 0x0030
    if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    return None


# ---- Linux details -----------------------------------------------------------

def os_release(path: str = "/etc/os-release") -> dict[str, str]:
    """Parse /etc/os-release (KEY=value lines) into a dict; {} if missing."""
    info = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep:
                    info[key] = value.strip('"\'')
    except OSError:
        pass
    return info


# How to install QEMU on each family of Linux distributions. Matched against
# ID and ID_LIKE in /etc/os-release: Ubuntu and Mint say ID_LIKE=debian,
# Rocky and Alma say "rhel centos fedora", openSUSE says "suse opensuse".
QEMU_PACKAGES = {
    "debian": ["apt-get", "install", "-y", "qemu-system-x86", "qemu-utils"],
    "fedora": ["dnf", "install", "-y", "qemu-system-x86", "qemu-img"],
    "suse":   ["zypper", "--non-interactive", "install", "qemu-x86", "qemu-tools"],
    "arch":   ["pacman", "-S", "--noconfirm", "--needed", "qemu-base"],
}


def qemu_install_command(release: dict[str, str]) -> list[str] | None:
    """The package-manager command that installs QEMU on this distro, or None."""
    families = [release.get("ID", "")] + release.get("ID_LIKE", "").split()
    # RHEL and its clones (which also say "fedora") only ship a cut-down
    # /usr/libexec/qemu-kvm without qemu-system-x86_64 or slow mode.
    if "rhel" in families:
        return None
    for family in families:
        if family in QEMU_PACKAGES:
            return QEMU_PACKAGES[family]
    return None


def cpu_info(path: str = "/proc/cpuinfo") -> tuple[str, str, set[str]]:
    """(model name, vendor id, feature flags) of the first CPU, from /proc/cpuinfo."""
    model, vendor, flags = "", "", set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                key, _, value = line.partition(":")
                key, value = key.strip(), value.strip()
                if key == "model name" and not model:
                    model = value
                elif key == "vendor_id" and not vendor:
                    vendor = value
                elif key == "flags" and not flags:
                    flags = set(value.split())
    except OSError:
        pass
    return model, vendor, flags


def read_text(path: str) -> str:
    """A small text file's contents, stripped; '' if it can't be read."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""
