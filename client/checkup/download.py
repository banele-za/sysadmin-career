"""Download the Linux image (and its SSH keys) on first launch.

A release is a folder on a web server (a GitHub Release, for now) with:

    manifest.json        which files to fetch, with their sizes and SHA-256
    alma10-base.qcow2    the base image (qcow2 with compression, QEMU reads it as is)
    game_root, player    the game's SSH private keys for that image

Each file is streamed to "<name>.part", checked against its SHA-256, and
only then renamed into place. An interrupted download never leaves a
half-written image behind, and a corrupted one is caught before QEMU sees it.

The keys are public anyway (every copy of the game needs them); the VM only
listens on 127.0.0.1, so they don't open anything to the network.
"""

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Callable

from client import config

CHUNK = 1024 * 1024
USER_AGENT = "sysadmin-career-game"

# Where each file in the manifest goes, relative to config.IMAGES_DIR.
DESTINATIONS = {
    config.BASE_IMAGE_NAME: Path(config.BASE_IMAGE_NAME),
    "game_root": Path("keys") / "game_root",
    "player": Path("keys") / "player",
}


class DownloadError(Exception):
    pass


def _open(url: str, timeout: float):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout)


def _join(base: str, name: str) -> str:
    return base.rstrip("/") + "/" + name


def fetch_manifest(base_url: str, timeout: float = 30) -> dict:
    with _open(_join(base_url, "manifest.json"), timeout) as response:
        manifest = json.loads(response.read())
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != set(DESTINATIONS):
        raise ValueError(f"manifest lists {sorted(files or {})}, expected {sorted(DESTINATIONS)}")
    return manifest


def download_all(base_url: str, target_dir: Path,
                 on_progress: Callable[[int, int], None] = lambda done, total: None) -> None:
    """Fetch every file in the manifest into target_dir. Blocking; run in a thread.

    on_progress(bytes_done, bytes_total) is called about once per megabyte.
    """
    manifest = fetch_manifest(base_url)
    total = sum(f["size"] for f in manifest["files"].values())
    done = 0
    # The image last: if it fails, the small key files are already there and
    # are simply fetched again next time.
    for name in sorted(manifest["files"], key=lambda n: n == config.BASE_IMAGE_NAME):
        info = manifest["files"][name]
        target = target_dir / DESTINATIONS[name]
        if target.exists() and target.stat().st_size == info["size"] and _sha256(target) == info["sha256"]:
            done += info["size"]
            on_progress(done, total)
            continue
        done = _fetch_file(_join(base_url, name), target, info, done, total, on_progress)


def _fetch_file(url, target: Path, info: dict, done: int, total: int, on_progress) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    try:
        with _open(url, timeout=60) as response, open(partial, "wb") as out:
            while chunk := response.read(CHUNK):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                on_progress(done, total)
    except OSError as e:
        partial.unlink(missing_ok=True)
        raise DownloadError(f"downloading {target.name} failed: {e}") from e
    if digest.hexdigest() != info["sha256"]:
        partial.unlink(missing_ok=True)
        raise DownloadError(f"{target.name} arrived damaged (checksum mismatch); please try again")
    partial.replace(target)
    return done


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()
