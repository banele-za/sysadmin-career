"""Pick the fastest way to run the VM on this computer.

Hardware acceleration lets the VM run at near-native speed:
  Windows -> WHPX, Linux -> KVM, macOS -> HVF.
If none works we fall back to TCG, QEMU's pure software CPU emulator
("slow mode" in the design doc). It always works, just 10-20x slower.

We don't trust feature flags alone: the only reliable test is to start
QEMU with the accelerator for a moment and see whether it stays up.
"""

import subprocess
import sys
from dataclasses import dataclass

from client import config


@dataclass
class Accel:
    name: str        # value for QEMU's -accel option
    cpu: str         # value for QEMU's -cpu option
    hardware: bool   # False means slow mode


# "host" passes the real CPU's features through. TCG can't do that, so it
# uses "max": every feature QEMU can emulate (enough for the x86_64_v2 image).
SOFTWARE = Accel(name="tcg", cpu="max", hardware=False)


def _hardware_candidate() -> Accel | None:
    if sys.platform == "win32":
        return Accel(name="whpx", cpu="host", hardware=True)
    if sys.platform.startswith("linux"):
        return Accel(name="kvm", cpu="host", hardware=True)
    if sys.platform == "darwin":
        return Accel(name="hvf", cpu="host", hardware=True)
    return None


def _probe(accel: Accel, seconds: float = 2.0) -> bool:
    """Start an empty QEMU machine with this accelerator; True if it survives."""
    cmd = [
        str(config.qemu_binary("qemu-system-x86_64")),
        "-accel", accel.name, "-cpu", accel.cpu,
        "-machine", "q35", "-m", "128",
        "-display", "none", "-nodefaults",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=seconds)
        return False          # it exited on its own: the accelerator failed
    except subprocess.TimeoutExpired:
        return True           # still running: the accelerator works
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def detect(force_software: bool = False) -> Accel:
    """Return the best working accelerator."""
    candidate = _hardware_candidate()
    if candidate and not force_software and _probe(candidate):
        return candidate
    return SOFTWARE
