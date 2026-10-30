"""Run the hidden game VM and reset it between tickets.

Lifecycle:
  start()  - boot QEMU. The first time ever, wait for Linux to finish
             booting and save a running snapshot called "clean".
             Every later start just loads that snapshot (seconds, not minutes).
  reset()  - get back to a fresh system, as fast as this PC allows (below).
  stop()   - shut QEMU down.

How reset() works depends on what the accelerator supports:

  1. Snapshots work (slow mode / TCG): restart QEMU straight into "clean".
     About 4 seconds.
  2. No snapshots (WHPX can't save them) but a warm spare is allowed: a
     second VM has already cold-booted a fresh disk in the background while
     the player worked. Swap to it (about a second) and start booting the
     next spare on the old disk.
  3. Neither: throw the disk away and cold-boot (about 23 seconds).

Why restart QEMU instead of loading the snapshot into the running one?
QEMU's built-in network (slirp) keeps timers and connection state that a
snapshot load doesn't rewind. After a few in-place loads the VM stopped
answering SSH. A new QEMU process started with -loadvm has fresh network
state every time and costs only about a second more.

Each VM's disk is a thin overlay on the downloaded base image (see
qemu.create_overlay), so the base image is never modified.
"""

import asyncio
import subprocess
import time
from pathlib import Path
from typing import Callable

import asyncssh

from client import config
from client.ssh import session
from client.vm import accel as accel_mod, childproc, qemu
from client.vm.qmp import QMPClient, QMPError


def _spare_path(path: Path) -> Path:
    """overlay.qcow2 -> overlay-spare.qcow2 (same for the logs)."""
    return path.with_name(f"{path.stem}-spare{path.suffix}")


class _Machine:
    """One QEMU process with its own overlay disk, logs and ports."""

    def __init__(self, disk: Path, serial_log: Path, qemu_log: Path):
        self.disk = disk
        self.serial_log = serial_log
        self.qemu_log = qemu_log
        self.ssh_port: int | None = None
        self.proc: subprocess.Popen | None = None
        self.qmp: QMPClient | None = None

    async def launch(self, accel: accel_mod.Accel, memory_mb: int, loadvm: str | None = None) -> None:
        """Start QEMU; with `loadvm`, it resumes from that snapshot instead of booting."""
        self.ssh_port = qemu.free_port()
        qmp_port = qemu.free_port()
        spec = qemu.VMSpec(
            disk=self.disk,
            accel=accel,
            ssh_port=self.ssh_port,
            qmp_port=qmp_port,
            serial_log=self.serial_log,
            memory_mb=memory_mb,
            extra=["-loadvm", loadvm] if loadvm else [],
        )
        self.qemu_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.qemu_log, "w") as log:
            # childproc.start: if the game dies, this QEMU dies with it.
            self.proc = childproc.start(qemu.command(spec), stdout=log, stderr=subprocess.STDOUT)
        qmp = QMPClient()
        try:
            await qmp.connect(qmp_port)
        except OSError:
            raise RuntimeError(f"QEMU failed to start: {self.qemu_log.read_text().strip()}")
        self.qmp = qmp     # only once connected: stop() relies on that

    async def wait_for_boot(self, timeout: float) -> None:
        conn = await session.wait_until_up(self.ssh_port, "root", config.ROOT_KEY, timeout)
        # Wait for every boot service to settle, so the system is calm.
        # ("degraded" exits non-zero; that's fine for our purposes.)
        await conn.run("systemctl is-system-running --wait", timeout=timeout)
        conn.close()
        await conn.wait_closed()

    def fresh_disk(self, base: Path) -> None:
        self.disk.unlink(missing_ok=True)
        qemu.create_overlay(base, self.disk)

    async def stop(self) -> None:
        if self.qmp:
            try:
                await self.qmp.execute("quit")
            except (QMPError, OSError):
                pass
            await self.qmp.close()
            self.qmp = None
        elif self.proc:
            self.proc.kill()      # no control connection (cancelled mid-launch): no polite way
        if self.proc:
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None


class VMManager:
    def __init__(self, on_status: Callable[[str], None] = print, force_software: bool = False,
                 accel: accel_mod.Accel | None = None, memory_mb: int = config.VM_MEMORY_MB,
                 warm_spare: bool = False):
        self.on_status = on_status          # the UI passes a function to show progress
        self.force_software = force_software
        self.accel = accel                  # None: detect it in start()
        self.memory_mb = memory_mb
        self.warm_spare = warm_spare        # allowed to run a standby VM (needs spare RAM)
        self.snapshots_work = True
        self.is_clean = False               # True right after start/reset, until root() is used
        self._current = _Machine(config.OVERLAY_DISK, config.SERIAL_LOG, config.QEMU_LOG)
        self._other = _Machine(_spare_path(config.OVERLAY_DISK), _spare_path(config.SERIAL_LOG),
                               _spare_path(config.QEMU_LOG))
        self._spare_task: asyncio.Task | None = None   # boots self._other in the background
        self._root: asyncssh.SSHClientConnection | None = None

    @property
    def ssh_port(self) -> int | None:
        return self._current.ssh_port

    @property
    def spare_active(self) -> bool:
        return self._spare_task is not None

    # ---- public API ------------------------------------------------------

    async def start(self) -> None:
        if not config.BASE_IMAGE.exists():
            raise FileNotFoundError(f"Base image missing: {config.BASE_IMAGE}")
        if self.accel is None:
            self.accel = accel_mod.detect(self.force_software)
        self.on_status(f"Starting VM ({'fast' if self.accel.hardware else 'slow'} mode, {self.accel.name})")

        self._discard_overlay_if_stale()
        disk = self._current.disk
        have_snapshot = disk.exists() and config.CLEAN_SNAPSHOT in qemu.list_snapshots(disk)
        if have_snapshot:
            try:
                await self._load_clean()
                self.is_clean = True
                return
            except (RuntimeError, QMPError, TimeoutError) as e:
                # A snapshot taken under another accelerator, or a broken one.
                self.on_status(f"Snapshot unusable ({e}); rebuilding it")
                await self._cold_boot(self._current)
        else:
            # No snapshot: whatever is on the overlay is leftovers from last
            # session. A fresh overlay is the clean state.
            await self._cold_boot(self._current)
        await self._save_clean()
        self.is_clean = True
        if not self.snapshots_work and self.warm_spare:
            self._start_spare()

    async def reset(self) -> None:
        """Bring the VM back to the clean state (no-op if nothing touched it yet)."""
        await self._close_root()
        if self.is_clean:
            return
        if self.snapshots_work:
            await self._load_clean()
        elif self._spare_task:
            await self._swap_to_spare()
        else:
            await self._cold_boot(self._current)
        self.is_clean = True

    async def root(self) -> asyncssh.SSHClientConnection:
        """An SSH connection as root, for break.sh and grade.sh.

        Anything done as root may change the VM, so the next reset() must
        really reset it.
        """
        self.is_clean = False
        if self._root is None:
            self._root = await session.connect(self.ssh_port, "root", config.ROOT_KEY)
        return self._root

    async def stop(self) -> None:
        await self._close_root()
        await self._cancel_spare()
        await self._current.stop()
        await self._other.stop()

    # ---- internals -------------------------------------------------------

    @property
    def _boot_timeout(self) -> float:
        return 180 if self.accel.hardware else 1200

    async def _cold_boot(self, machine: _Machine, quiet: bool = False) -> None:
        """Discard the machine's disk and boot the base image from scratch."""
        await machine.stop()
        machine.fresh_disk(config.BASE_IMAGE)
        if not quiet:
            self.on_status("Booting Linux...")
        started = time.monotonic()
        await machine.launch(self.accel, self.memory_mb)
        await machine.wait_for_boot(self._boot_timeout)
        if not quiet:
            self.on_status(f"Booted in {time.monotonic() - started:.0f}s")

    async def _save_clean(self) -> None:
        if not self.snapshots_work:
            return
        self.on_status("Saving clean snapshot...")
        started = time.monotonic()
        try:
            await self._current.qmp.run_job("snapshot-save", "save-clean", timeout=600,
                                            tag=config.CLEAN_SNAPSHOT, vmstate="disk0", devices=["disk0"])
        except (QMPError, TimeoutError) as e:
            self.snapshots_work = False
            self.on_status(f"Snapshots not supported here ({e}); resets will reboot instead")
            return
        await self._ensure_running()
        self.on_status(f"Snapshot saved in {time.monotonic() - started:.1f}s")

    async def _load_clean(self) -> None:
        """Restart QEMU directly into the clean snapshot (see module docstring)."""
        started = time.monotonic()
        await self._current.stop()
        await self._current.launch(self.accel, self.memory_mb, loadvm=config.CLEAN_SNAPSHOT)
        await self._ensure_running()
        await self._sync_clock()
        self.on_status(f"VM reset in {time.monotonic() - started:.1f}s")

    async def _ensure_running(self) -> None:
        status = await self._current.qmp.execute("query-status")
        if status["status"] != "running":
            await self._current.qmp.execute("cont")

    async def _sync_clock(self) -> None:
        """The restored VM thinks it's still the moment the snapshot was taken; fix its clock."""
        conn = await session.wait_until_up(self.ssh_port, "root", config.ROOT_KEY, 60)
        await conn.run(f"date -s @{time.time():.3f} >/dev/null")
        self._root = conn

    # ---- warm spare --------------------------------------------------------

    def _start_spare(self) -> None:
        """Cold-boot the other machine in the background, ready for the next reset."""
        self._spare_task = asyncio.create_task(self._cold_boot(self._other, quiet=True))

    async def _swap_to_spare(self) -> None:
        started = time.monotonic()
        if not self._spare_task.done():
            self.on_status("Getting a fresh server ready...")
        try:
            await self._spare_task
        except Exception as e:  # the spare failed to boot: fall back to a normal cold boot
            self.on_status(f"Standby server failed ({e}); rebooting instead")
            self._spare_task = None
            await self._cold_boot(self._current)
            self._start_spare()
            return
        # Swap: the spare becomes current; the old one becomes the next spare.
        old = self._current
        self._current, self._other = self._other, old
        await old.stop()
        self._start_spare()
        self.on_status(f"VM reset in {time.monotonic() - started:.1f}s")

    async def _cancel_spare(self) -> None:
        if self._spare_task:
            self._spare_task.cancel()
            try:
                await self._spare_task
            except (asyncio.CancelledError, Exception):
                pass
            self._spare_task = None

    # ---- housekeeping --------------------------------------------------------

    def _discard_overlay_if_stale(self) -> None:
        """Delete the overlay if it wasn't made on the current base image.

        An overlay only stores differences from the base image it was created
        on. On another base those differences (and the snapshot) are garbage.
        Two ways that happens:
          - the base was rebuilt or re-downloaded. The overlay file is written
            every time the VM runs, so it's always newer than its base,
            unless the base was replaced since;
          - the base now lives elsewhere (a developer's images/out build vs
            the downloaded copy the installed game uses).
        """
        overlay = self._current.disk
        if not overlay.exists():
            return
        if overlay.stat().st_mtime < config.BASE_IMAGE.stat().st_mtime:
            self.on_status("Base image was rebuilt; starting from a fresh disk")
            overlay.unlink()
        elif not qemu.same_file(qemu.backing_file(overlay), config.BASE_IMAGE):
            self.on_status("Base image moved; starting from a fresh disk")
            overlay.unlink()

    async def _close_root(self) -> None:
        if self._root:
            self._root.close()
            self._root = None
