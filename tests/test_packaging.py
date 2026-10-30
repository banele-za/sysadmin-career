"""The Windows packaging helpers. (The full build is tested by hand: see README.)"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging" / "windows"))
vendor_qemu = pytest.importorskip("vendor_qemu")       # needs pefile (requirements-build.txt)

from client.vm import qemu  # noqa: E402


def test_qemu_source_url_points_at_the_exact_commit():
    version = "QEMU emulator version 11.1.0 (v11.1.0-12130-ge470268ff4)"
    assert vendor_qemu.source_url(version) == "https://gitlab.com/qemu-project/qemu/-/tree/e470268ff4"
    assert vendor_qemu.source_url("QEMU emulator version 9.2.0") == "https://download.qemu.org/"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows paths")
def test_same_file_ignores_case_and_slashes():
    assert qemu.same_file(Path(r"C:\Data\Base.qcow2"), Path("c:/data/base.qcow2"))
    assert not qemu.same_file(Path(r"C:\Data\base.qcow2"), Path(r"C:\Other\base.qcow2"))
    assert not qemu.same_file(None, Path(r"C:\Data\base.qcow2"))
