"""Run the hidden game VM and reset it between tickets.

Lifecycle:
  start()  - boot QEMU. The first time ever, wait for Linux to finish
             booting and save a running snapshot called "clean".
             Every later start just loads that snapshot (seconds, not minutes).
  reset()  - restart QEMU straight into "clean": a fresh system in seconds.
  stop()   - shut QEMU down.

The snapshot lives inside the overlay disk (see qemu.create_overlay), so the
downloaded base image is never modified.

Why restart QEMU instead of loading the snapshot into the running one?
QEMU's built-in network (slirp) keeps timers and connection state that a
snapshot load doesn't rewind. After a few in-place loads the VM stopped
answering SSH. A new QEMU process started with -loadvm has fresh network
state every time and costs only about a second more.

If snapshots don't work with this accelerator (WHPX can't save them),
reset() falls back to throwing away the overlay and cold-booting, which is
slower but always works.
"""

import subprocess
import time
from typing import Callable

import asyncssh

from client import config
from client.ssh import session
from client.vm import accel, qemu
from client.vm.qmp import QMPClient, QMPError


class VMManager:
    def __init__(self, on_status: Callable[[str], None] = print, force_software: bool = False):
        self.on_status = on_status          # the UI passes a function to show progress
        self.force_software = force_software
        self.accel: accel.Accel | None = None
        self.ssh_port: int | None = None
        self.snapshots_work = True
        self.is_clean = False                # True right after start/reset, until root() is used
        self._proc: subprocess.Popen | None = None
        self._qmp: QMPClient | None = None
        self._root: asyncssh.SSHClientConnection | None = None

    # ---- public API ------------------------------------------------------

    async def start(self) -> None:
        if not config.BASE_IMAGE.exists():
            raise FileNotFoundError(f"Base image missing: {config.BASE_IMAGE}. Run images/build_rhel.py.")
        self.accel = accel.detect(self.force_software)
        self.on_status(f"Starting VM ({'fast' if self.accel.hardware else 'slow'} mode, {self.accel.name})")

        self._discard_overlay_if_stale()
        have_snapshot = (config.OVERLAY_DISK.exists() and
                         config.CLEAN_SNAPSHOT in qemu.list_snapshots(config.OVERLAY_DISK))
        if have_snapshot:
            try:
                await self._load_clean()
                self.is_clean = True
                return
            except (RuntimeError, QMPError, TimeoutError) as e:
                # A snapshot taken under another accelerator, or a broken one.
                self.on_status(f"Snapshot unusable ({e}); rebuilding it")
                await self._recreate_overlay_and_boot()
        else:
            # No snapshot: whatever is on the overlay is leftovers from last
            # session. A fresh overlay is the clean state.
            config.OVERLAY_DISK.unlink(missing_ok=True)
            qemu.create_overlay(config.BASE_IMAGE, config.OVERLAY_DISK)
            await self._launch()
            await self._wait_for_boot()
        await self._save_clean()
        self.is_clean = True

    async def reset(self) -> None:
        """Bring the VM back to the clean state (no-op if nothing touched it yet)."""
        await self._close_root()
        if self.is_clean:
            return
        if self.snapshots_work:
            await self._load_clean()
        else:
            await self._recreate_overlay_and_boot()
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
        if self._qmp:
            try:
                await self._qmp.execute("quit")
            except (QMPError, OSError):
                pass
            await self._qmp.close()
            self._qmp = None
        if self._proc:
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    # ---- internals -------------------------------------------------------

    @property
    def _boot_timeout(self) -> float:
        return 180 if self.accel.hardware else 1200

    async def _launch(self, loadvm: str | None = None) -> None:
        """Start QEMU; with `loadvm`, it resumes from that snapshot instead of booting."""
        self.ssh_port = qemu.free_port()
        qmp_port = qemu.free_port()
        spec = qemu.VMSpec(
            disk=config.OVERLAY_DISK,
            accel=self.accel,
            ssh_port=self.ssh_port,
            qmp_port=qmp_port,
            serial_log=config.SERIAL_LOG,
            extra=["-loadvm", loadvm] if loadvm else [],
        )
        # CREATE_NO_WINDOW stops a console window flashing up on Windows.
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        config.QEMU_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(config.QEMU_LOG, "w") as log:
            self._proc = subprocess.Popen(qemu.command(spec), creationflags=flags,
                                          stdout=log, stderr=subprocess.STDOUT)
        self._qmp = QMPClient()
        try:
            await self._qmp.connect(qmp_port)
        except OSError:
            raise RuntimeError(f"QEMU failed to start: {config.QEMU_LOG.read_text().strip()}")

    async def _wait_for_boot(self) -> None:
        self.on_status("Booting Linux (first time only)...")
        started = time.monotonic()
        conn = await session.wait_until_up(self.ssh_port, "root", config.ROOT_KEY, self._boot_timeout)
        # Wait for every boot service to settle so the snapshot is a calm system.
        # ("degraded" exits non-zero; that's fine for our purposes.)
        await conn.run("systemctl is-system-running --wait", timeout=self._boot_timeout)
        conn.close()
        await conn.wait_closed()
        self.on_status(f"Booted in {time.monotonic() - started:.0f}s")

    async def _save_clean(self) -> None:
        if not self.snapshots_work:
            return
        self.on_status("Saving clean snapshot...")
        started = time.monotonic()
        try:
            await self._qmp.run_job("snapshot-save", "save-clean", timeout=600,
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
        await self.stop()
        await self._launch(loadvm=config.CLEAN_SNAPSHOT)
        await self._ensure_running()
        await self._sync_clock()
        self.on_status(f"VM reset in {time.monotonic() - started:.1f}s")

    async def _ensure_running(self) -> None:
        status = await self._qmp.execute("query-status")
        if status["status"] != "running":
            await self._qmp.execute("cont")

    async def _sync_clock(self) -> None:
        """The restored VM thinks it's still the moment the snapshot was taken; fix its clock."""
        conn = await session.wait_until_up(self.ssh_port, "root", config.ROOT_KEY, 60)
        await conn.run(f"date -s @{time.time():.3f} >/dev/null")
        self._root = conn

    def _discard_overlay_if_stale(self) -> None:
        """Delete the overlay if the base image was rebuilt after it was made.

        An overlay only stores differences from the base image it was created
        on. On a new base those differences (and the snapshot) are garbage.
        The overlay file is written every time the VM runs, so it's always
        newer than its base, unless the base was replaced since.
        """
        overlay = config.OVERLAY_DISK
        if overlay.exists() and overlay.stat().st_mtime < config.BASE_IMAGE.stat().st_mtime:
            self.on_status("Base image was rebuilt; starting from a fresh disk")
            overlay.unlink()

    async def _recreate_overlay_and_boot(self) -> None:
        """Slow reset path: discard every change and cold-boot the base image."""
        await self.stop()
        config.OVERLAY_DISK.unlink(missing_ok=True)
        qemu.create_overlay(config.BASE_IMAGE, config.OVERLAY_DISK)
        await self._launch()
        await self._wait_for_boot()

    async def _close_root(self) -> None:
        if self._root:
            self._root.close()
            self._root = None
