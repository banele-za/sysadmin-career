"""A QEMU that can't start is reported at once, with its reason (needs QEMU, not the image)."""

import asyncio
import time

import pytest

from client import config
from client.vm import accel
from client.vm.manager import _Machine


def _qemu_installed() -> bool:
    try:
        config.find_qemu_dir()
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _qemu_installed(), reason="QEMU not installed")
def test_qemu_that_exits_fails_fast_with_its_reason(tmp_path):
    # The disk file doesn't exist, so QEMU exits straight away.
    machine = _Machine(tmp_path / "missing-disk.qcow2", tmp_path / "serial.log", tmp_path / "qemu.log")
    t0 = time.monotonic()
    with pytest.raises(RuntimeError) as failure:
        asyncio.run(machine.launch(accel.SOFTWARE, memory_mb=128))
    assert time.monotonic() - t0 < 15                  # not the 2-minute patience for slow starts
    message = str(failure.value)
    assert "exit code" in message and "missing-disk.qcow2" in message   # QEMU's own reason
