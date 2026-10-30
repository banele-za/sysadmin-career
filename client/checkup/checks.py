"""Turn the facts about this PC into green / yellow / red checks.

Pure logic, no measuring (that's facts.py), so every case is unit-testable.

The design doc's promise: nobody is locked out. Missing hardware
acceleration is never a dead end, it means slow mode. Only things the game
truly can't work around are "blocking": no QEMU, not enough disk, or no image.

The smoke test has the final word. If QEMU runs with acceleration, the
virtualization checks are green no matter what Windows' flags say (on this
developer's PC, Windows reports "Windows Hypervisor Platform: disabled" while
WHPX works fine).
"""

from dataclasses import asdict, dataclass, field

from client import config
from client.checkup.facts import GB, Facts

GREEN, YELLOW, RED = "green", "yellow", "red"

# Actions a check can offer. The UI shows them as buttons; game.py runs them.
ACTION_LABELS = {
    "enable_feature": "Turn it on",
    "bios_guide": "Show me how",
    "kvm_fix": "Fix it",
    "install_qemu": "Install it",
    "download": "Download",
    "retry": "Check again",
}


@dataclass
class Check:
    key: str
    title: str
    status: str                  # GREEN / YELLOW / RED
    message: str                 # one plain-English sentence
    actions: list = field(default_factory=list)
    blocking: bool = False       # True: the game can't start until it's fixed


@dataclass
class Checkup:
    checks: list[Check]
    mode: str                    # "fast" or "slow"
    vm_memory_mb: int
    warm_spare: bool             # room for a standby VM (see vm/manager.py)

    @property
    def blocking(self) -> bool:
        return any(c.blocking for c in self.checks)

    @property
    def all_green(self) -> bool:
        return all(c.status == GREEN for c in self.checks)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["blocking"] = self.blocking
        d["all_green"] = self.all_green
        for c in d["checks"]:
            c["actions"] = [{"id": a, "label": ACTION_LABELS[a]} for a in c["actions"]]
        return d


def evaluate(f: Facts) -> Checkup:
    checks = [_qemu(f)]
    if f.platform == "win32":
        checks.append(_windows_feature(f))
    checks.append(_firmware(f))
    if f.platform.startswith("linux"):
        checks.append(_kvm_permissions(f))
    ram = _ram(f)
    checks += [ram, _disk(f), _image(f), _smoke(f)]

    ram_gb = f.ram_bytes / GB
    small = 0 < ram_gb < config.RAM_COMFORTABLE_GB
    return Checkup(
        checks=checks,
        mode="fast" if f.smoke_ok else "slow",
        vm_memory_mb=config.VM_MEMORY_SMALL_MB if small else config.VM_MEMORY_MB,
        # A standby VM only makes sense with real acceleration and RAM to spare.
        warm_spare=f.smoke_ok and ram_gb >= config.RAM_WARM_SPARE_GB,
    )


# ---- the checks --------------------------------------------------------------

def _qemu(f: Facts) -> Check:
    title = "Virtual machine program (QEMU)"
    if f.qemu_found:
        return Check("qemu", title, GREEN, "Installed.")
    if f.platform.startswith("linux"):
        return Check("qemu", title, RED,
                     "The game runs its Linux server with QEMU, which isn't installed yet.",
                     actions=["install_qemu", "retry"], blocking=True)
    # Windows builds ship QEMU inside the game folder, so it's only missing if
    # that folder is damaged (or a developer hasn't installed it).
    return Check("qemu", title, RED,
                 "QEMU is missing from the game's folder. Reinstalling the game fixes this.",
                 actions=["retry"], blocking=True)


def _windows_feature(f: Facts) -> Check:
    title = "Windows virtualization setting"
    if f.smoke_ok:
        return Check("feature", title, GREEN, "Windows is set up for fast mode.")
    # Only the feature flags count here: with the BIOS switch off the
    # hypervisor can't run either, which says nothing about this setting.
    if f.windows_features.get("HypervisorPlatform") in ("disabled", "absent"):
        return Check("feature", title, RED,
                     "A Windows setting needs to be turned on for fast mode.",
                     actions=["enable_feature"])
    return Check("feature", title, GREEN, "The Windows setting is on.")


def _firmware(f: Facts) -> Check:
    title = "Virtualization in BIOS"
    # A running hypervisor proves the BIOS switch is on.
    if f.smoke_ok or f.hypervisor_present or f.firmware_virt or f.kvm_exists:
        return Check("firmware", title, GREEN, "Your computer's speed boost is switched on.")
    if f.host_is_vm:
        # Inside a VM the BIOS guide can't help: the outer system decides
        # whether virtualization is passed through ("nested virtualization").
        return Check("firmware", title, YELLOW,
                     "This Linux is itself running in a virtual machine (such as WSL) that "
                     "doesn't pass the speed boost through, so the game uses slow mode.")
    if f.firmware_virt is False or f.kvm_exists is False:
        return Check("firmware", title, RED,
                     "Your computer's speed boost is switched off in the BIOS.",
                     actions=["bios_guide"])
    return Check("firmware", title, YELLOW,
                 "Couldn't tell whether the speed boost is on in the BIOS.",
                 actions=["bios_guide"])


def _kvm_permissions(f: Facts) -> Check:
    title = "Permission to use KVM"
    if f.smoke_ok or f.kvm_accessible or not f.kvm_exists:
        return Check("kvm", title, GREEN, "You're allowed to use hardware virtualization.")
    return Check("kvm", title, RED, "Your user isn't allowed to use KVM yet.", actions=["kvm_fix"])


def _ram(f: Facts) -> Check:
    title = "Memory (RAM)"
    gb = f.ram_bytes / GB
    if not f.ram_bytes:
        return Check("ram", title, YELLOW, "Couldn't read how much memory this PC has; using defaults.")
    if gb < config.RAM_COMFORTABLE_GB:
        return Check("ram", title, YELLOW,
                     f"{gb:.0f} GB is a little tight, so the server gets "
                     f"{config.VM_MEMORY_SMALL_MB // 1024} GB instead of "
                     f"{config.VM_MEMORY_MB // 1024}. Close other apps if it feels slow.")
    return Check("ram", title, GREEN, f"{gb:.0f} GB, plenty.")


def _disk(f: Facts) -> Check:
    title = "Disk space"
    need = config.WORK_SPACE_GB * GB
    if not f.image_present:
        need += f.download_size_bytes
    if f.disk_free_bytes < need:
        short = (need - f.disk_free_bytes) / GB
        return Check("disk", title, RED,
                     f"Please free up {short:.1f} GB more on the drive with "
                     f"{_drive_label()} ({need / GB:.1f} GB needed, "
                     f"{f.disk_free_bytes / GB:.1f} GB free).",
                     actions=["retry"], blocking=True)
    return Check("disk", title, GREEN, f"{f.disk_free_bytes / GB:.0f} GB free.")


def _image(f: Facts) -> Check:
    title = "Linux server image"
    if f.image_present:
        return Check("image", title, GREEN, "Downloaded and ready.")
    if not f.download_configured:
        return Check("image", title, RED,
                     "No download server is set up in this build. "
                     "(Developers: run images/build_rhel.py.)",
                     actions=["retry"], blocking=True)
    if not f.download_reachable:
        return Check("image", title, RED,
                     "Can't reach the download server. Check your internet connection.",
                     actions=["retry"], blocking=True)
    size = f.download_size_bytes / GB
    return Check("image", title, YELLOW,
                 f"Needs a one-time download ({size:.1f} GB).",
                 actions=["download"], blocking=True)


def _smoke(f: Facts) -> Check:
    title = "Speed test"
    if f.smoke_ok:
        return Check("smoke", title, GREEN, "Fast mode works.")
    return Check("smoke", title, YELLOW,
                 "Fast mode isn't available yet, so the game will run in slow mode. "
                 "That works fine, tickets just take a little longer to load.",
                 actions=["retry"])


def _drive_label() -> str:
    """'C:' on Windows, else the data folder itself."""
    drive = config.DATA_DIR.drive
    return drive if drive else str(config.DATA_DIR)
