"""Checkup logic with made-up facts, the downloader against a local web
server, the BIOS guides and the diagnostic report. No VM needed."""

import functools
import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest

from client import config
from client.checkup import checks, download, guides, report
from client.checkup.checks import GREEN, RED, YELLOW
from client.checkup.facts import GB, Facts


def healthy(**changes) -> Facts:
    """A Windows PC where everything works; tweak one thing per test."""
    f = Facts(platform="win32", manufacturer="Acer", cpu_vendor="amd",
              ram_bytes=16 * GB, disk_free_bytes=100 * GB,
              firmware_virt=True, hypervisor_present=True,
              windows_features={"HypervisorPlatform": "enabled", "VirtualMachinePlatform": "enabled"},
              image_present=True, smoke_ok=True, smoke_accel="whpx")
    for key, value in changes.items():
        setattr(f, key, value)
    return f


def status(checkup, key):
    return next(c for c in checkup.checks if c.key == key)


def test_all_green():
    c = checks.evaluate(healthy())
    assert c.all_green and not c.blocking
    assert (c.mode, c.vm_memory_mb, c.warm_spare) == ("fast", 2048, True)


def test_smoke_test_overrides_windows_flags():
    # Seen on the developer's PC: the flag says disabled, WHPX works anyway.
    c = checks.evaluate(healthy(windows_features={"HypervisorPlatform": "disabled"}))
    assert status(c, "feature").status == GREEN and c.mode == "fast"


def test_feature_off_offers_one_click_fix():
    c = checks.evaluate(healthy(smoke_ok=False, hypervisor_present=False,
                                windows_features={"HypervisorPlatform": "disabled"}))
    feature = status(c, "feature")
    assert feature.status == RED and feature.actions == ["enable_feature"]
    assert status(c, "firmware").status == GREEN        # BIOS reports virtualization on
    assert c.mode == "slow" and not c.blocking          # never locked out
    assert not c.warm_spare


def test_bios_off_offers_guide():
    c = checks.evaluate(healthy(smoke_ok=False, hypervisor_present=False, firmware_virt=False))
    firmware = status(c, "firmware")
    assert firmware.status == RED and firmware.actions == ["bios_guide"]
    assert status(c, "smoke").status == YELLOW and not c.blocking


def test_unknown_bios_state_is_yellow():
    c = checks.evaluate(healthy(smoke_ok=False, hypervisor_present=None, firmware_virt=None))
    assert status(c, "firmware").status == YELLOW


def test_low_ram_shrinks_vm_and_drops_spare():
    c = checks.evaluate(healthy(ram_bytes=4 * GB))
    assert status(c, "ram").status == YELLOW
    assert c.vm_memory_mb == config.VM_MEMORY_SMALL_MB and not c.warm_spare


def test_seven_gb_keeps_full_vm_but_no_spare():
    c = checks.evaluate(healthy(ram_bytes=7 * GB))
    assert c.vm_memory_mb == config.VM_MEMORY_MB and not c.warm_spare


def test_low_disk_blocks_with_exact_amount():
    c = checks.evaluate(healthy(image_present=False, download_configured=True,
                                download_reachable=True, download_size_bytes=1 * GB,
                                disk_free_bytes=2 * GB))
    disk = status(c, "disk")
    assert disk.status == RED and disk.blocking
    assert "1.0 GB more" in disk.message          # needs 2 GB work space + 1 GB image


def test_missing_image_needs_download():
    c = checks.evaluate(healthy(image_present=False, download_configured=True,
                                download_reachable=True, download_size_bytes=GB // 2))
    image = status(c, "image")
    assert image.status == YELLOW and image.actions == ["download"] and c.blocking


def test_offline_means_retry():
    c = checks.evaluate(healthy(image_present=False, download_configured=True, download_reachable=False))
    assert status(c, "image").actions == ["retry"]


def test_linux_kvm_permission():
    c = checks.evaluate(healthy(platform="linux", smoke_ok=False, kvm_exists=True,
                                kvm_accessible=False, hypervisor_present=None, firmware_virt=None))
    assert status(c, "kvm").actions == ["kvm_fix"]
    assert status(c, "firmware").status == GREEN       # /dev/kvm exists, so the BIOS is fine
    assert not any(ch.key == "feature" for ch in c.checks)


def test_as_dict_labels_actions():
    d = checks.evaluate(healthy(smoke_ok=False, firmware_virt=False, hypervisor_present=False)).as_dict()
    firmware = next(c for c in d["checks"] if c["key"] == "firmware")
    assert firmware["actions"] == [{"id": "bios_guide", "label": "Show me how"}]
    json.dumps(d)                                     # must be sendable to the UI


# ---- guides ------------------------------------------------------------------

@pytest.mark.parametrize("maker, brand", [
    ("Acer", "Acer"), ("HP", "HP"), ("Hewlett-Packard", "HP"), ("LENOVO", "Lenovo"),
    ("Micro-Star International Co., Ltd.", "MSI"), ("System manufacturer", "your PC"),
])
def test_guide_matching(maker, brand):
    assert guides.find_guide(maker)["brand"] == brand


def test_every_guide_builds():
    for path in guides.GUIDES_DIR.glob("*.yaml"):
        g = guides.find_guide(path.stem)
        for vendor in ("intel", "amd", ""):
            built = guides.build(g["brand"], vendor)
            assert len(built["steps"]) == 5


# ---- report ------------------------------------------------------------------

def test_report_hides_home_folder():
    f = healthy(smoke_error=f"failed reading {Path.home() / 'x'}")
    text = report.build(f, checks.evaluate(f), extra_error="boom")
    assert str(Path.home()) not in text
    assert "== checks" in text and "error: boom" in text


# ---- download ----------------------------------------------------------------

@pytest.fixture
def release_server(tmp_path):
    """Serve a tiny fake release (a few KB 'image') over HTTP on localhost."""
    folder = tmp_path / "release"
    folder.mkdir()
    contents = {config.BASE_IMAGE_NAME: b"qcow2!" * 500_000, "game_root": b"root key", "player": b"player key"}
    files = {}
    for name, data in contents.items():
        (folder / name).write_bytes(data)
        files[name] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (folder / "manifest.json").write_text(json.dumps({"format": 1, "files": files}))

    handler = functools.partial(_QuietHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/", folder, contents
    server.shutdown()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def test_download_verifies_and_places_files(release_server, tmp_path):
    url, _, contents = release_server
    target = tmp_path / "images"
    progress = []
    download.download_all(url, target, on_progress=lambda done, total: progress.append((done, total)))
    assert (target / config.BASE_IMAGE_NAME).read_bytes() == contents[config.BASE_IMAGE_NAME]
    assert (target / "keys" / "player").read_bytes() == b"player key"
    assert progress[-1][0] == progress[-1][1] == sum(len(d) for d in contents.values())
    assert not list(target.rglob("*.part"))


def test_damaged_download_is_rejected(release_server, tmp_path):
    url, folder, _ = release_server
    (folder / config.BASE_IMAGE_NAME).write_bytes(b"corrupt" * 1000)    # no longer matches manifest
    target = tmp_path / "images"
    with pytest.raises(download.DownloadError, match="damaged"):
        download.download_all(url, target)
    assert not (target / config.BASE_IMAGE_NAME).exists()
    assert not list(target.rglob("*.part"))


def test_bad_manifest_rejected(release_server):
    url, folder, _ = release_server
    (folder / "manifest.json").write_text(json.dumps({"files": {"evil.exe": {"size": 1, "sha256": ""}}}))
    with pytest.raises(ValueError):
        download.fetch_manifest(url)


class _StallingHandler(_QuietHandler):
    """Like GitHub's file servers on a bad day: the first connection for the
    image sends half of it, then goes silent. Later connections may ask to
    resume (HTTP Range) and get the rest straight away."""
    stalled = threading.Event()
    range_requests: list = []

    def do_GET(self):
        path = self.translate_path(self.path)
        if not path.endswith(config.BASE_IMAGE_NAME):
            return super().do_GET()
        data = open(path, "rb").read()
        start = 0
        if self.headers.get("Range"):
            start = int(self.headers["Range"].split("=")[1].rstrip("-"))
            self.range_requests.append(start)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(len(data) - start))
        self.end_headers()
        if not self.stalled.is_set():
            self.stalled.set()
            self.wfile.write(data[:len(data) // 2])
            self.wfile.flush()
            threading.Event().wait(10)            # silence (longer than the stall timeout)
            return
        self.wfile.write(data[start:])


def test_stalled_download_resumes_on_a_new_connection(release_server, tmp_path, monkeypatch):
    url, folder, contents = release_server
    monkeypatch.setattr(download, "STALL_SECONDS", 1)
    _StallingHandler.stalled.clear()
    _StallingHandler.range_requests.clear()
    handler = functools.partial(_StallingHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        target = tmp_path / "images"
        download.download_all(f"http://127.0.0.1:{server.server_address[1]}/", target)
        image = contents[config.BASE_IMAGE_NAME]
        assert (target / config.BASE_IMAGE_NAME).read_bytes() == image
        assert _StallingHandler.range_requests == [len(image) // 2]   # resumed, not restarted
    finally:
        server.shutdown()


def test_partial_download_is_kept_for_next_time(release_server, tmp_path):
    """Quitting mid-download keeps the .part file; the next try continues it."""
    url, _, contents = release_server
    image = contents[config.BASE_IMAGE_NAME]
    target = tmp_path / "images"
    target.mkdir()
    (target / (config.BASE_IMAGE_NAME + ".part")).write_bytes(image[:1000])
    download.download_all(url, target)      # (this test server ignores Range: it restarts, still correct)
    assert (target / config.BASE_IMAGE_NAME).read_bytes() == image
