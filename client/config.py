"""Where everything lives on disk, and a few VM sizing settings.

Every path the game uses is defined here, so nothing else has to guess.
Environment variables let you override paths during development.
"""

import os
import shutil
from pathlib import Path

from client import host

# The repository root (the folder that contains client/, content/, images/).
REPO_ROOT = Path(__file__).resolve().parent.parent

CONTENT_DIR = REPO_ROOT / "content"
TICKETS_DIR = CONTENT_DIR / "tickets"
UI_DIR = REPO_ROOT / "client" / "ui"

DATA_DIR = host.data_dir()     # save file, VM disks, downloaded image

# The base image and the game's SSH keys. Developers build them with
# images/build_rhel.py (into images/out/); players download them on first
# launch (into the data folder). A local build wins if there is one.
IMAGES_OUT = REPO_ROOT / "images" / "out"
BASE_IMAGE_NAME = "alma10-base.qcow2"
IMAGES_DIR = IMAGES_OUT if (IMAGES_OUT / BASE_IMAGE_NAME).exists() else DATA_DIR / "images"
BASE_IMAGE = IMAGES_DIR / BASE_IMAGE_NAME
KEYS_DIR = IMAGES_DIR / "keys"
ROOT_KEY = KEYS_DIR / "game_root"      # the game uses this to run break/grade as root
PLAYER_KEY = KEYS_DIR / "player"       # the player's terminal logs in with this
PLAYER_USER = "admin"

# Where the image download lives: a folder URL holding manifest.json and the
# files it lists (made by images/release.py, uploaded to a GitHub Release).
# A new image means a new release tag here. Override with SYSADMIN_GAME_IMAGE_URL.
IMAGE_RELEASE_URL = os.environ.get(
    "SYSADMIN_GAME_IMAGE_URL",
    "https://github.com/banele-za/sysadmin-career/releases/download/image-v1")

SAVE_DB = DATA_DIR / "save.db"
OVERLAY_DISK = DATA_DIR / "vm" / "overlay.qcow2"   # thin layer on top of BASE_IMAGE
SERIAL_LOG = DATA_DIR / "vm" / "serial.log"        # the VM's console output, for debugging
QEMU_LOG = DATA_DIR / "vm" / "qemu.log"            # QEMU's own warnings and errors
GAME_LOG = DATA_DIR / "game.log"                   # Python errors, for the diagnostic report
DIAGNOSTIC_REPORT = DATA_DIR / "diagnostic-report.txt"

# VM size. 2 GB matches the design doc; the checkup shrinks it on small PCs.
VM_MEMORY_MB = 2048
VM_MEMORY_SMALL_MB = 1024
VM_CPUS = 2

# RAM thresholds (total physical memory) used by the checkup.
RAM_COMFORTABLE_GB = 6     # below this the VM gets VM_MEMORY_SMALL_MB
RAM_WARM_SPARE_GB = 8      # a second, standby VM needs this much

# Disk the VM's working files need on top of the image (overlay disks grow).
WORK_SPACE_GB = 2

# Name of the running snapshot we restore between tickets.
CLEAN_SNAPSHOT = "clean"


def find_qemu_dir() -> Path:
    """Locate the folder holding qemu-system-x86_64 and qemu-img.

    Search order: $SYSADMIN_GAME_QEMU, a bundled vendor/qemu folder (packaged
    Windows builds ship QEMU there), the standard Windows install path, then
    PATH (on Linux: the distro's QEMU package, usually in /usr/bin).
    """
    candidates = []
    if os.environ.get("SYSADMIN_GAME_QEMU"):
        candidates.append(Path(os.environ["SYSADMIN_GAME_QEMU"]))
    candidates.append(REPO_ROOT / "vendor" / "qemu")
    if host.WINDOWS:
        candidates.append(Path(r"C:\Program Files\qemu"))
    on_path = shutil.which("qemu-system-x86_64")
    if on_path:
        candidates.append(Path(on_path).parent)

    exe = host.exe_name("qemu-system-x86_64")
    for folder in candidates:
        if (folder / exe).exists():
            return folder
    install = ("winget install SoftwareFreedomConservancy.QEMU" if host.WINDOWS
               else "your distribution's qemu package")
    raise FileNotFoundError(
        f"QEMU not found. Install it ({install}) "
        "or set SYSADMIN_GAME_QEMU to the folder containing qemu-system-x86_64."
    )


def qemu_binary(name: str) -> Path:
    """Full path to a QEMU tool, e.g. qemu_binary('qemu-img')."""
    return find_qemu_dir() / host.exe_name(name)
