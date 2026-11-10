"""Download the Linux image (and its SSH keys) on first launch.

A release is a folder on a web server (a GitHub Release, for now) with:

    manifest.json        which files to fetch, with their sizes and SHA-256
    alma10-base.qcow2    the base image (qcow2 with compression, QEMU reads it as is)
    game_root, player    the game's SSH private keys for that image

Each file is streamed to "<name>.part", checked against its SHA-256, and
only then renamed into place. An interrupted download never leaves a
half-written image behind, and a corrupted one is caught before QEMU sees it.

Big downloads stall. Sometimes one connection to GitHub's file servers
slows to a trickle while a fresh one is fast. So if a connection goes quiet
or crawls, we drop it and open a new one that *resumes* where the .part
file ends (an HTTP "Range" request). The .part file is also kept when the
game quits mid-download, so the next launch continues instead of
starting over.

The keys are public anyway (every copy of the game needs them); the VM only
listens on 127.0.0.1, so they don't open anything to the network.
"""

import hashlib
import http.client
import json
import time
import urllib.request
from pathlib import Path
from typing import Callable

from client import config

CHUNK = 1024 * 1024
USER_AGENT = "sysadmin-career-game"

# When to give up on one connection and resume on a fresh one:
STALL_SECONDS = 15            # no data at all for this long
SLOW_WINDOW_SECONDS = 20      # ...or, measured over this long,
SLOW_MIN_BYTES = 1024 * 1024  # less than this arrived (a trickle: under ~50 KB/s)
# Connections that bring no data at all, per file, before reporting failure.
# (A slow line just keeps reconnecting while it makes progress; that's fine.)
MAX_FRUITLESS_CONNECTIONS = 8

# Where each file in the manifest goes, relative to config.IMAGES_DIR.
DESTINATIONS = {
    config.BASE_IMAGE_NAME: Path(config.BASE_IMAGE_NAME),
    "game_root": Path("keys") / "game_root",
    "player": Path("keys") / "player",
}


class DownloadError(Exception):
    pass


def _open(url: str, timeout: float, start: int = 0):
    """Open url; with start > 0, ask for the file from that byte on."""
    headers = {"User-Agent": USER_AGENT}
    if start:
        headers["Range"] = f"bytes={start}-"
    request = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(request, timeout=timeout)


class _TooSlow(Exception):
    """This connection crawls; drop it and resume on a new one."""


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
    """Download one file into target, resuming on fresh connections as needed.

    `done` is the byte count of earlier files (for the overall progress);
    returns it plus this file's size.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    size = info["size"]
    if partial.exists() and partial.stat().st_size > size:
        partial.unlink()                          # not ours to resume
    last_error: Exception | None = None
    fruitless = 0
    have = partial.stat().st_size if partial.exists() else 0
    while have < size and fruitless < MAX_FRUITLESS_CONNECTIONS:
        before = have
        try:
            _read_into(url, partial, have, lambda n: on_progress(done + n, total))
            ended_cleanly = True
        except (OSError, http.client.HTTPException, _TooSlow) as e:   # stalled, crawled, dropped: resume
            last_error, ended_cleanly = e, False
        have = partial.stat().st_size if partial.exists() else 0
        if ended_cleanly and have != size:
            # The server sent its whole file, and it's not the size the
            # manifest promised: a different file, not a network hiccup.
            partial.unlink(missing_ok=True)
            raise DownloadError(f"{target.name} arrived damaged (wrong size); please try again")
        if have <= before:
            fruitless += 1
            time.sleep(min(fruitless, 5))         # give a flaky network a moment
        else:
            fruitless = 0
    if have != size:
        raise DownloadError(f"downloading {target.name} kept stalling ({have} of {size} bytes; "
                            f"last problem: {last_error}). Try again; it continues where it stopped.")
    if _sha256(partial) != info["sha256"]:
        partial.unlink()
        raise DownloadError(f"{target.name} arrived damaged (checksum mismatch); please try again")
    partial.replace(target)
    return done + size


def _read_into(url: str, partial: Path, have: int, progress: Callable[[int], None]) -> None:
    """One connection: append to partial from byte `have` until the end, or
    until the connection stalls (socket timeout) or crawls (_TooSlow)."""
    with _open(url, timeout=STALL_SECONDS, start=have) as response:
        if have and response.status != 206:       # server ignored the Range: start over
            have = 0
        with open(partial, "ab" if have else "wb") as out:
            window_start, window_bytes = time.monotonic(), 0
            # read1: whatever has arrived (up to CHUNK), so a trickle is noticed in time.
            while chunk := response.read1(CHUNK):
                out.write(chunk)
                have += len(chunk)
                window_bytes += len(chunk)
                progress(have)
                if time.monotonic() - window_start >= SLOW_WINDOW_SECONDS:
                    if window_bytes < SLOW_MIN_BYTES:
                        raise _TooSlow(f"{window_bytes} bytes in {SLOW_WINDOW_SECONDS} s")
                    window_start, window_bytes = time.monotonic(), 0


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()
