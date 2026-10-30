"""One-click fixes the checkup offers.

Every fix that changes the system asks for admin rights first, so the
player always sees and approves it: the UAC prompt on Windows, pkexec's
password dialog on Linux. Nothing here runs silently.

When SYSADMIN_GAME_FAKE is set, fixes only *describe* what they would do,
so the unhappy paths can be tested without touching the real PC.
"""

import getpass
import shlex
import subprocess
from dataclasses import dataclass

from client import host
from client.checkup.facts import fake_problems

# Both features: QEMU's WHPX needs Windows Hypervisor Platform, and on some
# Windows versions that relies on Virtual Machine Platform being on as well.
WINDOWS_FEATURES = ["HypervisorPlatform", "VirtualMachinePlatform"]


@dataclass
class FixResult:
    ok: bool
    message: str            # shown to the player
    needs_restart: bool = False


def _faking() -> bool:
    return bool(fake_problems())


def _powershell(command: str, timeout: float = 600) -> subprocess.CompletedProcess:
    return host.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                    capture_output=True, text=True, timeout=timeout)


def enable_windows_feature() -> FixResult:
    """Turn on the Windows features fast mode needs (UAC prompt, then restart)."""
    enable = "; ".join(f"Enable-WindowsOptionalFeature -Online -FeatureName {name} -All -NoRestart -ErrorAction Stop"
                       for name in WINDOWS_FEATURES)
    if _faking():
        return FixResult(True, f"(Test mode: would run as admin: {enable})", needs_restart=True)
    # Start-Process -Verb RunAs shows the UAC prompt and runs an elevated
    # PowerShell; -Wait blocks until it's done, -PassThru gives its exit code.
    # Inside the elevated shell, any error ends it with exit code 1.
    inner = f"try {{ {enable} | Out-Null; exit 0 }} catch {{ exit 1 }}"
    outer = (f"$p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
             f"-ArgumentList '-NoProfile','-Command','{inner}'; exit $p.ExitCode")
    try:
        result = _powershell(outer)
    except subprocess.TimeoutExpired:
        return FixResult(False, "Turning the setting on took too long. Try again, or play in slow mode.")
    if result.returncode == 0:
        return FixResult(True, "Done! Windows needs a restart to finish turning it on.",
                         needs_restart=True)
    # Declining the UAC prompt makes Start-Process itself fail.
    if "canceled" in result.stderr.lower() or "cancelled" in result.stderr.lower():
        return FixResult(False, "No changes made (the admin prompt was declined).")
    return FixResult(False, "Windows couldn't turn the setting on. The BIOS guide may help, "
                            "or you can play in slow mode.")


def _as_admin(command: list[str], success: str, timeout: float = 900) -> FixResult:
    """Linux: run `command` as root via pkexec, which shows a password dialog.

    pkexec needs a desktop "polkit agent" to draw that dialog. Without one
    (a bare terminal, WSL) it fails, and we tell the player the sudo command
    to type instead.
    """
    by_hand = "sudo " + shlex.join(command)
    if _faking():
        return FixResult(True, f"(Test mode: would run as admin: {by_hand})", needs_restart=True)
    try:
        result = subprocess.run(["pkexec"] + command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return FixResult(False, f"Couldn't ask for admin rights. In a terminal, run: {by_hand}")
    if result.returncode == 0:
        return FixResult(True, success, needs_restart=True)
    # pkexec's own exit codes: 126 = the player cancelled, 127 = no agent / not allowed.
    if result.returncode == 126:
        return FixResult(False, "No changes made (the admin prompt was cancelled).")
    return FixResult(False, f"That didn't work. In a terminal, run: {by_hand}")


def fix_kvm_permissions() -> FixResult:
    """Linux: add the user to the kvm group."""
    return _as_admin(["usermod", "-aG", "kvm", getpass.getuser()],
                     "Done! Log out and back in for it to take effect.")


def install_qemu() -> FixResult:
    """Linux: install the distro's QEMU package (the game uses it to run the VM)."""
    command = host.qemu_install_command(host.os_release())
    if command is None:
        return FixResult(False, "The game doesn't know how to install QEMU on this Linux "
                                "distribution. Install qemu-system-x86_64 and qemu-img with "
                                "your package manager, then press Check again.")
    result = _as_admin(command, "QEMU is installed.")
    result.needs_restart = False         # nothing to restart: press Check again
    return result


def restart_computer(into_firmware: bool = False) -> FixResult:
    """Restart now; with into_firmware, straight into the BIOS/UEFI setup.

    Restarting into the firmware only works on UEFI PCs. Older BIOS
    machines refuse, and the guide then explains the key to press during
    startup instead.
    """
    command = host.restart_command(into_firmware)
    if _faking():
        return FixResult(True, f"(Test mode: would run {' '.join(command)})")
    try:
        result = host.run(command, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return FixResult(False, f"Restart failed: {e}")
    if result.returncode == 0:
        return FixResult(True, "Restarting in 5 seconds..." if host.WINDOWS else "Restarting...")
    if into_firmware:
        return FixResult(False, "This PC can't restart straight into the BIOS. Restart it "
                                "normally and press the key shown in the guide while it starts.")
    return FixResult(False, f"Restart failed: {result.stderr.strip()}")
