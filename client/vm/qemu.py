"""Build QEMU command lines and manage disk files.

Kept separate from the manager so you can read exactly which options we
pass to QEMU and why, in one place.
"""

import socket
from dataclasses import dataclass, field
from pathlib import Path

from client import config, host
from client.vm.accel import Accel


def free_port() -> int:
    """Ask the OS for an unused TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _escape(value: str) -> str:
    """QEMU option values separate keys with commas; a literal comma is ',,'."""
    return value.replace(",", ",,")


@dataclass
class VMSpec:
    disk: Path
    accel: Accel
    ssh_port: int                      # host port forwarded to the VM's port 22
    qmp_port: int | None = None        # host port for the QMP control socket
    serial_log: Path | None = None     # where the VM's console output goes
    memory_mb: int = config.VM_MEMORY_MB
    cpus: int = config.VM_CPUS
    smbios_serial: str | None = None   # used by the image build to point cloud-init at its config
    extra: list[str] = field(default_factory=list)


def command(spec: VMSpec) -> list[str]:
    """Turn a VMSpec into the qemu-system-x86_64 argument list."""
    cmd = [
        str(config.qemu_binary("qemu-system-x86_64")),
        "-name", "sysadmin-game",
        "-machine", "q35",
        "-accel", spec.accel.name,
        "-cpu", spec.accel.cpu,
        "-smp", str(spec.cpus),
        "-m", str(spec.memory_mb),
        # The disk. Naming the node "disk0" lets QMP refer to it for snapshots.
        "-blockdev", f"driver=file,filename={_escape(str(spec.disk))},node-name=disk0-file",
        "-blockdev", "driver=qcow2,file=disk0-file,node-name=disk0",
        "-device", "virtio-blk-pci,drive=disk0",
        # User-mode networking: the VM gets internet through QEMU, and
        # localhost:<ssh_port> on this computer reaches the VM's sshd.
        "-netdev", f"user,id=net0,hostfwd=tcp:127.0.0.1:{spec.ssh_port}-:22",
        "-device", "virtio-net-pci,netdev=net0",
        # Entropy for the guest, so sshd and crypto don't stall at boot.
        "-device", "virtio-rng-pci",
        # No window: the player only ever sees our terminal.
        "-display", "none",
        "-serial", f"file:{spec.serial_log}" if spec.serial_log else "null",
    ]
    if spec.qmp_port is not None:
        cmd += ["-qmp", f"tcp:127.0.0.1:{spec.qmp_port},server=on,wait=off"]
    if spec.smbios_serial:
        cmd += ["-smbios", f"type=1,serial={_escape(spec.smbios_serial)}"]
    return cmd + spec.extra


def create_overlay(base: Path, overlay: Path) -> None:
    """Make a thin qcow2 disk that reads from `base` and stores only changes.

    The base image is never written to, so deleting the overlay is a full
    factory reset.
    """
    overlay.parent.mkdir(parents=True, exist_ok=True)
    host.run(
        [str(config.qemu_binary("qemu-img")), "create", "-q", "-f", "qcow2",
         "-b", str(base), "-F", "qcow2", str(overlay)],
        check=True,
    )


def list_snapshots(disk: Path) -> list[str]:
    """Names of the internal snapshots in a qcow2 file (VM must be stopped)."""
    out = host.run(
        [str(config.qemu_binary("qemu-img")), "snapshot", "-l", str(disk)],
        check=True, capture_output=True, text=True,
    ).stdout
    # Output: a header, a column line, then "ID  TAG  VM_SIZE ..." rows.
    names = []
    for line in out.splitlines()[2:]:
        parts = line.split()
        if len(parts) >= 2:
            names.append(parts[1])
    return names
