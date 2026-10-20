"""Where everything lives on disk, and a few VM sizing settings.

Every path the game uses is defined here, so nothing else has to guess.
Environment variables let you override paths during development.
"""

import os
import shutil
from pathlib import Path

# The repository root (the folder that contains client/, content/, images/).
REPO_ROOT = Path(__file__).resolve().parent.parent

CONTENT_DIR = REPO_ROOT / "content"
TICKETS_DIR = CONTENT_DIR / "tickets"
UI_DIR = REPO_ROOT / "client" / "ui"

# Output of images/build_rhel.py: the base image and the game's SSH keys.
IMAGES_OUT = REPO_ROOT / "images" / "out"
BASE_IMAGE = IMAGES_OUT / "alma10-base.qcow2"
KEYS_DIR = IMAGES_OUT / "keys"
ROOT_KEY = KEYS_DIR / "game_root"      # the game uses this to run break/grade as root
PLAYER_KEY = KEYS_DIR / "player"       # the player's terminal logs in with this
PLAYER_USER = "admin"


def _default_data_dir() -> Path:
    """Per-user folder for the save file and the VM's working disk."""
    override = os.environ.get("SYSADMIN_GAME_DATA")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")  # Windows
    if local:
        return Path(local) / "SysadminGame"
    return Path.home() / ".local" / "share" / "sysadmin-game"


DATA_DIR = _default_data_dir()
SAVE_DB = DATA_DIR / "save.db"
OVERLAY_DISK = DATA_DIR / "vm" / "overlay.qcow2"   # thin layer on top of BASE_IMAGE
SERIAL_LOG = DATA_DIR / "vm" / "serial.log"        # the VM's console output, for debugging
QEMU_LOG = DATA_DIR / "vm" / "qemu.log"            # QEMU's own warnings and errors

# VM size. 2 GB matches the design doc; slow mode may shrink this later (M2).
VM_MEMORY_MB = 2048
VM_CPUS = 2

# Name of the running snapshot we restore between tickets.
CLEAN_SNAPSHOT = "clean"


def find_qemu_dir() -> Path:
    """Locate the folder holding qemu-system-x86_64 and qemu-img.

    Search order: $SYSADMIN_GAME_QEMU, a bundled vendor/qemu folder (used
    by packaged builds later), the standard Windows install path, then PATH.
    """
    candidates = []
    if os.environ.get("SYSADMIN_GAME_QEMU"):
        candidates.append(Path(os.environ["SYSADMIN_GAME_QEMU"]))
    candidates.append(REPO_ROOT / "vendor" / "qemu")
    candidates.append(Path(r"C:\Program Files\qemu"))
    on_path = shutil.which("qemu-system-x86_64")
    if on_path:
        candidates.append(Path(on_path).parent)

    exe = "qemu-system-x86_64.exe" if os.name == "nt" else "qemu-system-x86_64"
    for folder in candidates:
        if (folder / exe).exists():
            return folder
    raise FileNotFoundError(
        "QEMU not found. Install it (winget install SoftwareFreedomConservancy.QEMU) "
        "or set SYSADMIN_GAME_QEMU to the folder containing qemu-system-x86_64."
    )


def qemu_binary(name: str) -> Path:
    """Full path to a QEMU tool, e.g. qemu_binary('qemu-img')."""
    suffix = ".exe" if os.name == "nt" else ""
    return find_qemu_dir() / f"{name}{suffix}"
