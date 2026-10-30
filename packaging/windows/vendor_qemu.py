"""Copy just the parts of QEMU the game needs into vendor/qemu.

A full QEMU install for Windows is about 1.2 GB: emulators for 30 kinds of
CPU, firmware for all of them, documentation. The game needs one emulator
(qemu-system-x86_64), qemu-img for disk files, the DLLs those two load,
and the few firmware files a q35 PC with our devices reads at startup.

Which DLLs? Each .exe/.dll lists the DLLs it imports. We follow that list
recursively (with the pefile library), keeping every DLL that sits in the
QEMU folder. DLLs not found there (kernel32.dll and friends) belong to
Windows itself.

    .venv\\Scripts\\python packaging\\windows\\vendor_qemu.py ["C:\\Program Files\\qemu"]
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pefile

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "vendor" / "qemu"

PROGRAMS = ["qemu-system-x86_64.exe", "qemu-img.exe"]

# Firmware read from the share folder by our VM (see client/vm/qemu.py):
FIRMWARE = [
    "bios-256k.bin",        # SeaBIOS, the PC's BIOS
    "kvmvapic.bin",         # interrupt-controller speed-up for older guests
    "linuxboot_dma.bin",    # option ROM the q35 machine always loads
    "vgabios-stdvga.bin",   # BIOS of the default VGA card
    "efi-virtio.rom",       # boot ROM of the virtio network card
    "edk2-licenses.txt",    # not firmware: licences of the firmware above's sources
]


def imported_dlls(path: Path) -> list[str]:
    """Names of the DLLs a Windows program or DLL loads at startup."""
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    names = [entry.dll.decode() for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])]
    pe.close()
    return names


def dll_closure(source: Path, programs: list[str]) -> set[str]:
    """Every DLL in `source` that `programs` need, directly or indirectly."""
    in_folder = {p.name.lower(): p.name for p in source.glob("*.dll")}
    needed: set[str] = set()
    todo = list(programs)
    while todo:
        for dll in imported_dlls(source / todo.pop()):
            name = in_folder.get(dll.lower())
            if name and name not in needed:
                needed.add(name)
                todo.append(name)
    return needed


def source_url(version: str) -> str:
    """Where this exact QEMU's source code is.

    'QEMU emulator version 11.1.0 (v11.1.0-12130-ge470268ff4)': the part
    after "-g" is the git commit it was built from.
    """
    match = re.search(r"-g([0-9a-f]{7,40})\)", version)
    if match:
        return f"https://gitlab.com/qemu-project/qemu/-/tree/{match.group(1)}"
    return "https://download.qemu.org/"


def vendor(source: Path) -> None:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    (TARGET / "share").mkdir(parents=True)

    dlls = dll_closure(source, PROGRAMS)
    for name in PROGRAMS + sorted(dlls):
        shutil.copy2(source / name, TARGET / name)
    for name in FIRMWARE:
        shutil.copy2(source / "share" / name, TARGET / "share" / name)
    for name in ("COPYING", "COPYING.LIB"):                 # QEMU's licences (GPL-2.0, LGPL)
        shutil.copy2(source / name, TARGET / name)

    # The exact version, so anyone can fetch the matching source code
    # (THIRD-PARTY.md promises this file).
    version = subprocess.run([str(TARGET / PROGRAMS[0]), "--version"],
                             capture_output=True, text=True, check=True).stdout.splitlines()[0]
    (TARGET / "VERSION").write_text(f"{version}\nSource code: {source_url(version)}\n", encoding="utf-8")

    size = sum(f.stat().st_size for f in TARGET.rglob("*") if f.is_file())
    print(f"{len(PROGRAMS)} programs, {len(dlls)} DLLs, {len(FIRMWARE)} share files: "
          f"{size / 2**20:.0f} MB in {TARGET}")
    print(version)


if __name__ == "__main__":
    vendor(Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\qemu"))
