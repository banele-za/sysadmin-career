"""Collect raw facts about this computer for the checkup.

This module only *measures*. Deciding what the facts mean (green, yellow,
red) is checks.py's job, so that logic can be tested with made-up facts.

Everything here works without admin rights. On Windows one PowerShell call
reads WMI (the Windows Management Instrumentation database); it takes a few
seconds, so it runs in parallel with the QEMU smoke test.

Testing the unhappy paths: set SYSADMIN_GAME_FAKE to a comma-separated list
of problems to pretend this PC has, e.g.

    $env:SYSADMIN_GAME_FAKE = "feature-off,low-ram"

  feature-off  Windows virtualization features disabled (fast mode fails)
  bios-off     virtualization switched off in the BIOS (fast mode fails)
  low-ram      only 4 GB of RAM
  tiny-ram     only 3 GB of RAM
  low-disk     only 1 GB free
  no-image     the Linux image hasn't been downloaded yet
  offline      the download server can't be reached
  no-qemu      QEMU isn't installed (Linux: offers the one-click install)
  kvm-denied   Linux: /dev/kvm exists but this user may not use it
"""

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from client import config, host
from client.vm import accel

FAKE_PROBLEMS = {"feature-off", "bios-off", "low-ram", "tiny-ram", "low-disk", "no-image",
                 "offline", "no-qemu", "kvm-denied"}
GB = 1024 ** 3


@dataclass
class Facts:
    platform: str                          # sys.platform: "win32" or "linux"
    os_name: str = ""
    manufacturer: str = ""                 # PC maker, picks the BIOS guide
    model: str = ""
    cpu: str = ""
    cpu_vendor: str = ""                   # "intel", "amd" or ""
    ram_bytes: int = 0
    disk_free_bytes: int = 0
    # Virtualization. None means "couldn't tell".
    firmware_virt: bool | None = None      # BIOS/UEFI switch (Intel VT-x / AMD-V)
    hypervisor_present: bool | None = None # Windows' hypervisor is running
    windows_features: dict = field(default_factory=dict)  # name -> "enabled" / "disabled" / "absent"
    kvm_exists: bool | None = None         # Linux
    kvm_accessible: bool | None = None     # Linux
    qemu_found: bool = True                # the program that runs the VM (Linux: a distro package)
    # Image and download.
    image_present: bool = False
    download_configured: bool = False
    download_reachable: bool | None = None
    download_size_bytes: int = 0
    # The final word: does QEMU actually run with hardware acceleration?
    smoke_ok: bool = False
    smoke_accel: str = ""
    smoke_error: str = ""
    fake: list = field(default_factory=list)  # SYSADMIN_GAME_FAKE problems applied

    def as_dict(self) -> dict:
        return asdict(self)


def fake_problems() -> set[str]:
    raw = os.environ.get("SYSADMIN_GAME_FAKE", "")
    wanted = {p.strip() for p in raw.split(",") if p.strip()}
    unknown = wanted - FAKE_PROBLEMS
    if unknown:
        raise ValueError(f"SYSADMIN_GAME_FAKE: unknown problems {sorted(unknown)}")
    return wanted


def gather() -> Facts:
    """Measure everything. Blocking (a few seconds); call it from a thread."""
    facts = Facts(platform=sys.platform)
    with ThreadPoolExecutor(max_workers=3) as pool:
        system = pool.submit(_system_info)
        smoke = pool.submit(_smoke_test)
        download = pool.submit(_download_info)
        _apply_system(facts, system.result())
        facts.smoke_ok, facts.smoke_accel, facts.smoke_error = smoke.result()
        facts.download_configured, facts.download_reachable, facts.download_size_bytes = download.result()
    facts.qemu_found = _qemu_found()
    facts.image_present = config.BASE_IMAGE.exists() and config.ROOT_KEY.exists()
    facts.disk_free_bytes = shutil.disk_usage(_existing_parent(config.DATA_DIR)).free
    _apply_fakes(facts, fake_problems())
    return facts


# ---- individual measurements -------------------------------------------------

# One PowerShell call for all the WMI questions. Win32_OptionalFeature's
# InstallState: 1 = enabled, 2 = disabled, 3 = absent.
_WMI_SCRIPT = r"""
$cs  = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$os  = Get-CimInstance Win32_OperatingSystem
$features = @{}
foreach ($name in 'HypervisorPlatform', 'VirtualMachinePlatform', 'Microsoft-Hyper-V') {
    $f = Get-CimInstance Win32_OptionalFeature -Filter "Name='$name'"
    $features[$name] = if ($f) { $f.InstallState } else { 3 }
}
[ordered]@{
    manufacturer = $cs.Manufacturer; model = $cs.Model
    hypervisor_present = $cs.HypervisorPresent; ram = $cs.TotalPhysicalMemory
    cpu = $cpu.Name; cpu_vendor = $cpu.Manufacturer
    firmware_virt = $cpu.VirtualizationFirmwareEnabled
    os_name = "$($os.Caption) (build $($os.BuildNumber))"
    features = $features
} | ConvertTo-Json -Compress
"""


def _system_info() -> dict:
    if host.WINDOWS:
        return _windows_info()
    return _linux_info()


def _windows_info() -> dict:
    try:
        out = host.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _WMI_SCRIPT],
            capture_output=True, text=True, timeout=30,
        ).stdout
        return json.loads(out)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {}     # unknown facts stay None; the smoke test still decides


def _linux_info() -> dict:
    """The same facts as _WMI_SCRIPT, from Linux's own files."""
    release = host.os_release()
    cpu, vendor, _flags = host.cpu_info()
    info: dict = {
        "os_name": f"{release.get('PRETTY_NAME', 'Linux')} (kernel {os.uname().release})",
        # The firmware's own description of the PC; readable by any user.
        "manufacturer": host.read_text("/sys/class/dmi/id/sys_vendor"),
        "model": host.read_text("/sys/class/dmi/id/product_name"),
        "cpu": cpu, "cpu_vendor": vendor,          # "GenuineIntel" / "AuthenticAMD"
        "kvm_exists": os.path.exists("/dev/kvm"),
        "kvm_accessible": os.access("/dev/kvm", os.R_OK | os.W_OK),
    }
    try:
        info["ram"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        pass
    return info


def _apply_system(facts: Facts, info: dict) -> None:
    states = {1: "enabled", 2: "disabled", 3: "absent"}
    facts.manufacturer = (info.get("manufacturer") or "").strip()
    facts.model = (info.get("model") or "").strip()
    facts.cpu = (info.get("cpu") or "").strip()
    vendor = (info.get("cpu_vendor") or "").lower()
    facts.cpu_vendor = "amd" if "amd" in vendor else "intel" if "intel" in vendor else ""
    facts.ram_bytes = int(info.get("ram") or 0)
    facts.os_name = info.get("os_name", "")
    facts.firmware_virt = info.get("firmware_virt")
    facts.hypervisor_present = info.get("hypervisor_present")
    facts.windows_features = {name: states.get(v, "absent")
                              for name, v in (info.get("features") or {}).items()}
    facts.kvm_exists = info.get("kvm_exists")
    facts.kvm_accessible = info.get("kvm_accessible")


def _qemu_found() -> bool:
    try:
        config.find_qemu_dir()
        return True
    except FileNotFoundError:
        return False


def _smoke_test() -> tuple[bool, str, str]:
    """Start QEMU with hardware acceleration for a moment (see vm/accel.py)."""
    try:
        chosen = accel.detect()
    except FileNotFoundError as e:       # QEMU itself is missing (the qemu check says so)
        return False, "", str(e)
    if chosen.hardware:
        return True, chosen.name, ""
    return False, chosen.name, "QEMU exited straight away with hardware acceleration"


def _download_info() -> tuple[bool, bool | None, int]:
    """(configured, reachable, total size of the files to download)."""
    if not config.IMAGE_RELEASE_URL:
        return False, None, 0
    from client.checkup import download      # local import: avoids a cycle
    try:
        manifest = download.fetch_manifest(config.IMAGE_RELEASE_URL, timeout=10)
    except (OSError, ValueError):
        return True, False, 0
    return True, True, sum(f["size"] for f in manifest["files"].values())


def _existing_parent(path):
    while not path.exists():
        path = path.parent
    return path


def _apply_fakes(facts: Facts, problems: set[str]) -> None:
    facts.fake = sorted(problems)
    if problems & {"feature-off", "bios-off"}:
        facts.smoke_ok, facts.smoke_accel = False, "tcg"
        facts.smoke_error = "faked by SYSADMIN_GAME_FAKE"
        facts.hypervisor_present = False
    if "feature-off" in problems:
        facts.windows_features = {name: "disabled" for name in
                                  ("HypervisorPlatform", "VirtualMachinePlatform", "Microsoft-Hyper-V")}
    if "bios-off" in problems:
        facts.firmware_virt = False
    if "low-ram" in problems:
        facts.ram_bytes = 4 * GB
    if "tiny-ram" in problems:
        facts.ram_bytes = 3 * GB
    if "low-disk" in problems:
        facts.disk_free_bytes = 1 * GB
    if "no-image" in problems:
        facts.image_present = False
    if "offline" in problems:
        facts.download_configured, facts.download_reachable = True, False
    if "no-qemu" in problems:
        facts.qemu_found = False
        facts.smoke_ok, facts.smoke_accel = False, ""
        facts.smoke_error = "faked by SYSADMIN_GAME_FAKE"
    if "kvm-denied" in problems:
        facts.kvm_exists, facts.kvm_accessible = True, False
        facts.smoke_ok, facts.smoke_accel = False, "tcg"

