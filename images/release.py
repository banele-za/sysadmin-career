"""Package the built image for players to download.

    .venv\\Scripts\\python images\\release.py

Reads images/out/ (from build_rhel.py) and writes images/release/:

    alma10-base.qcow2   compressed copy of the base image
    game_root, player   the SSH private keys baked into that image
    manifest.json       size + SHA-256 of each file (the game checks these)

Upload all four files to one GitHub Release, then point the game at it:
    https://github.com/<owner>/<repo>/releases/download/<tag>/
(set config.IMAGE_RELEASE_URL, or SYSADMIN_GAME_IMAGE_URL while testing).

qcow2's built-in compression keeps the file small and QEMU reads it
directly, so players never have to unpack anything. New writes go to the
overlay disk, which is uncompressed, so speed isn't affected.
"""

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client import config  # noqa: E402

OUT = config.IMAGES_OUT
RELEASE = Path(__file__).resolve().parent / "release"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    source = OUT / config.BASE_IMAGE_NAME
    if not source.exists():
        sys.exit(f"{source} missing: run images/build_rhel.py first")
    RELEASE.mkdir(exist_ok=True)

    print("Compressing the image (a minute or two)...")
    started = time.monotonic()
    image = RELEASE / config.BASE_IMAGE_NAME
    subprocess.run([str(config.qemu_binary("qemu-img")), "convert", "-c", "-O", "qcow2",
                    str(source), str(image)], check=True)
    print(f"  {source.stat().st_size / 1e6:.0f} MB -> {image.stat().st_size / 1e6:.0f} MB "
          f"in {time.monotonic() - started:.0f}s")

    for key in ("game_root", "player"):
        shutil.copyfile(OUT / "keys" / key, RELEASE / key)

    files = {}
    for path in sorted(RELEASE.iterdir()):
        if path.name == "manifest.json":
            continue
        files[path.name] = {"size": path.stat().st_size, "sha256": sha256_of(path)}
    manifest = {"format": 1, "created": time.strftime("%Y-%m-%d"), "files": files}
    (RELEASE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Done: {RELEASE}")


if __name__ == "__main__":
    main()
