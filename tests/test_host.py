"""The Windows/Linux differences in client/host.py, and the Linux-only checks.

The Linux parsing is tested with sample files, so it runs on Windows too.
The real thing is tested on Linux itself (WSL2 for now).
"""

import pytest

from client import host
from client.checkup import checks, fixes
from client.checkup.checks import GREEN, RED
from client.checkup.facts import GB, Facts


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


# ---- /etc/os-release and installing QEMU ---------------------------------------

UBUNTU = 'NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.1 LTS"\nID=ubuntu\nID_LIKE=debian\n'
OPENSUSE = 'NAME="openSUSE Leap"\nID="opensuse-leap"\nID_LIKE="suse opensuse"\n'
ALMA = 'NAME="AlmaLinux"\nID="almalinux"\nID_LIKE="rhel centos fedora"\n'


def test_os_release_parsing(tmp_path):
    info = host.os_release(write(tmp_path, "os-release", UBUNTU + "# a comment\n\n"))
    assert info["PRETTY_NAME"] == "Ubuntu 24.04.1 LTS" and info["ID_LIKE"] == "debian"
    assert host.os_release(str(tmp_path / "missing")) == {}


@pytest.mark.parametrize("text, manager", [
    (UBUNTU, "apt-get"),
    (OPENSUSE, "zypper"),
    ("ID=fedora\n", "dnf"),
    ("ID=manjaro\nID_LIKE=arch\n", "pacman"),
])
def test_qemu_install_command_per_distro(tmp_path, text, manager):
    command = host.qemu_install_command(host.os_release(write(tmp_path, "os-release", text)))
    assert command[0] == manager


def test_rhel_clones_and_unknown_distros_get_no_command(tmp_path):
    # RHEL-likes also say "fedora", but don't ship qemu-system-x86_64.
    assert host.qemu_install_command(host.os_release(write(tmp_path, "a", ALMA))) is None
    assert host.qemu_install_command({"ID": "plan9"}) is None


def test_install_qemu_without_a_known_distro_explains(monkeypatch):
    monkeypatch.setattr(host, "os_release", lambda: {"ID": "plan9"})
    result = fixes.install_qemu()
    assert not result.ok and "package manager" in result.message


def test_install_qemu_in_test_mode_only_describes(monkeypatch):
    monkeypatch.setenv("SYSADMIN_GAME_FAKE", "no-qemu")
    monkeypatch.setattr(host, "os_release", lambda: {"ID": "ubuntu", "ID_LIKE": "debian"})
    result = fixes.install_qemu()
    assert result.ok and "sudo apt-get install -y qemu-system-x86" in result.message
    assert not result.needs_restart


# ---- /proc/cpuinfo --------------------------------------------------------------

CPUINFO = """processor\t: 0
vendor_id\t: AuthenticAMD
model name\t: AMD Ryzen 5 7535HS with Radeon Graphics
flags\t\t: fpu vme svm lm

processor\t: 1
vendor_id\t: AuthenticAMD
model name\t: AMD Ryzen 5 7535HS with Radeon Graphics
flags\t\t: fpu vme svm lm
"""


def test_cpu_info(tmp_path):
    model, vendor, flags = host.cpu_info(write(tmp_path, "cpuinfo", CPUINFO))
    assert model.startswith("AMD Ryzen 5") and vendor == "AuthenticAMD" and "svm" in flags


# ---- restarting ---------------------------------------------------------------

def test_restart_commands(monkeypatch):
    monkeypatch.setattr(host, "WINDOWS", True)
    assert host.restart_command(True) == ["shutdown", "/r", "/t", "5", "/fw"]
    monkeypatch.setattr(host, "WINDOWS", False)
    assert host.restart_command(False) == ["systemctl", "reboot"]
    assert host.restart_command(True)[-1] == "--firmware-setup"


# ---- data folder ------------------------------------------------------------

def test_data_dir_on_linux_follows_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("SYSADMIN_GAME_DATA", raising=False)
    monkeypatch.setattr(host, "WINDOWS", False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert host.data_dir() == tmp_path / "sysadmin-game"


# ---- the Linux checkup ------------------------------------------------------

def linux(**changes) -> Facts:
    """A Linux PC where everything works."""
    f = Facts(platform="linux", cpu_vendor="amd", ram_bytes=16 * GB, disk_free_bytes=100 * GB,
              kvm_exists=True, kvm_accessible=True, image_present=True,
              smoke_ok=True, smoke_accel="kvm")
    for key, value in changes.items():
        setattr(f, key, value)
    return f


def status(checkup, key):
    return next(c for c in checkup.checks if c.key == key)


def test_linux_all_green_has_no_windows_line():
    c = checks.evaluate(linux())
    assert c.all_green and c.mode == "fast"
    assert "feature" not in [check.key for check in c.checks]


def test_missing_qemu_blocks_with_install_button():
    c = checks.evaluate(linux(qemu_found=False, smoke_ok=False))
    qemu = status(c, "qemu")
    assert qemu.status == RED and qemu.blocking and qemu.actions[0] == "install_qemu"


def test_kvm_not_allowed_offers_fix_and_slow_mode():
    c = checks.evaluate(linux(kvm_accessible=False, smoke_ok=False))
    assert status(c, "kvm").actions == ["kvm_fix"]
    assert status(c, "firmware").status == GREEN       # /dev/kvm exists: BIOS is fine
    assert c.mode == "slow" and not c.blocking


def test_no_dev_kvm_points_at_the_bios():
    c = checks.evaluate(linux(kvm_exists=False, kvm_accessible=False, smoke_ok=False))
    assert status(c, "firmware").status == RED
    assert status(c, "kvm").status == GREEN            # nothing to grant permission to
