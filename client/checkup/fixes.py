"""One-click fixes the checkup offers.

Every fix that changes the system asks Windows for admin rights (the UAC
prompt), so the player always sees and approves it. Nothing here runs
silently.

When SYSADMIN_GAME_FAKE is set, fixes only *describe* what they would do,
so the unhappy paths can be tested without touching the real PC.
"""

import subprocess
import sys
from dataclasses import dataclass

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
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                          capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


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


def fix_kvm_permissions() -> FixResult:
    """Linux: add the user to the kvm group (graphical admin prompt via pkexec)."""
    import getpass
    command = ["pkexec", "usermod", "-aG", "kvm", getpass.getuser()]
    if _faking():
        return FixResult(True, f"(Test mode: would run {' '.join(command)})", needs_restart=True)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return FixResult(False, "Couldn't ask for admin rights. Run: sudo usermod -aG kvm $USER")
    if result.returncode == 0:
        return FixResult(True, "Done! Log out and back in for it to take effect.", needs_restart=True)
    return FixResult(False, "No changes made.")


def restart_computer(into_firmware: bool = False) -> FixResult:
    """Restart now; with into_firmware, straight into the BIOS/UEFI setup.

    `shutdown /r /fw` only works on UEFI PCs. Older BIOS machines refuse,
    and the guide then explains the key to press during startup instead.
    """
    if sys.platform != "win32":
        return FixResult(False, "Please restart your computer yourself.")
    command = ["shutdown", "/r", "/t", "5"] + (["/fw"] if into_firmware else [])
    if _faking():
        return FixResult(True, f"(Test mode: would run {' '.join(command)})")
    result = subprocess.run(command, capture_output=True, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode == 0:
        return FixResult(True, "Restarting in 5 seconds...")
    if into_firmware:
        return FixResult(False, "This PC can't restart straight into the BIOS. Restart it "
                                "normally and press the key shown in the guide while it starts.")
    return FixResult(False, f"Restart failed: {result.stderr.strip()}")
