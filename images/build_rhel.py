"""Build the Red Hat track base image (AlmaLinux 10, x86_64_v2).

Run from the repo root:
    .venv\\Scripts\\python images\\build_rhel.py

What it does:
  1. Creates the game's two SSH key pairs (root for the game, admin for the player).
  2. Downloads the pinned AlmaLinux cloud image and verifies its SHA-256.
  3. Copies it to images/out/alma10-base.qcow2 and grows the virtual disk.
  4. Boots it once in QEMU. cloud-init inside the VM fetches our settings
     (images/cloud-init/user-data) from a tiny web server this script runs,
     installs the keys and packages, enables sshd, then powers off.
  5. Checks the serial log for the success marker.

Cloud images normally get their settings from a cloud provider. Here we play
that role: QEMU's user-mode network lets the VM reach this computer at
10.0.2.2, and an SMBIOS serial number tells cloud-init where to look.
"""

import argparse
import hashlib
import http.server
import string
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

# Make "import client" work when this file is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncssh  # noqa: E402

from client import config  # noqa: E402
from client.vm import accel, qemu  # noqa: E402

# Pinned image: bump these three lines together to update the base OS.
IMAGE_NAME = "AlmaLinux-10-GenericCloud-10.2-20260817.0.x86_64_v2.qcow2"
IMAGE_SHA256 = "0bd83fd9c638cf78efee22f6245fe359a4d18b78efdec4975406bb7fd2b9a422"
IMAGE_URLS = [
    f"https://repo.almalinux.org/almalinux/10.2/cloud/x86_64_v2/images/{IMAGE_NAME}",
    # Old builds move to the vault once a newer point release ships.
    f"https://vault.almalinux.org/10.2/cloud/x86_64_v2/images/{IMAGE_NAME}",
]
DISK_SIZE = "20G"
SUCCESS_MARKER = "SYSADMIN-GAME-BUILD-OK"

HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache"


def ensure_keys() -> tuple[str, str]:
    """Create the game's SSH keys once; return (root_pubkey, player_pubkey)."""
    config.KEYS_DIR.mkdir(parents=True, exist_ok=True)
    pubkeys = []
    for path, comment in [(config.ROOT_KEY, "sysadmin-game-root"),
                          (config.PLAYER_KEY, "sysadmin-game-player")]:
        if not path.exists():
            key = asyncssh.generate_private_key("ssh-ed25519", comment=comment)
            key.write_private_key(str(path))
            key.write_public_key(str(path) + ".pub")
            print(f"  created key {path.name}")
        pubkeys.append(Path(str(path) + ".pub").read_text().strip())
    return pubkeys[0], pubkeys[1]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_image() -> Path:
    """Download the cloud image into images/cache/ unless a verified copy exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / IMAGE_NAME
    if target.exists() and sha256_of(target) == IMAGE_SHA256:
        print("  cached image verified")
        return target

    partial = target.with_suffix(".part")
    for url in IMAGE_URLS:
        print(f"  downloading {url}")
        try:
            with urllib.request.urlopen(url, timeout=60) as resp, open(partial, "wb") as out:
                total = int(resp.headers.get("Content-Length", 0))
                done = 0
                while chunk := resp.read(1024 * 1024):
                    out.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done * 100 // total:3d}%  {done >> 20} / {total >> 20} MB",
                              end="", flush=True)
            print()
        except OSError as e:
            print(f"\n  failed: {e}")
            continue
        if sha256_of(partial) != IMAGE_SHA256:
            partial.unlink()
            sys.exit("Checksum mismatch: the download is corrupt or the pin is wrong.")
        partial.replace(target)
        return target
    sys.exit("Could not download the image from any mirror.")


def serve_cloud_init(root_pub: str, player_pub: str) -> tuple[http.server.HTTPServer, int]:
    """Serve meta-data, user-data and vendor-data for cloud-init's NoCloud source."""
    template = string.Template((HERE / "cloud-init" / "user-data").read_text())
    files = {
        "/meta-data": "instance-id: sysadmin-game-build\nlocal-hostname: srv01\n",
        "/user-data": template.substitute(root_pubkey=root_pub, player_pubkey=player_pub),
        "/vendor-data": "",
        # Without this, cloud-init retries the URL ~20 times before giving up.
        "/network-config": "version: 2\nethernets:\n  nic0:\n    match: {name: \"e*\"}\n    dhcp4: true\n",
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = files.get(self.path)
            if body is None:
                self.send_error(404)
                return
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            print(f"  [cloud-init fetched] {self.path}")

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--software", action="store_true",
                        help="force software emulation (slow; for testing)")
    args = parser.parse_args()

    print("1/5 SSH keys")
    root_pub, player_pub = ensure_keys()

    print("2/5 Cloud image")
    cloud_image = download_image()

    print("3/5 Preparing disk")
    config.IMAGES_OUT.mkdir(parents=True, exist_ok=True)
    work = config.IMAGES_OUT / "alma10-base.building.qcow2"
    qemu_img = str(config.qemu_binary("qemu-img"))
    subprocess.run([qemu_img, "convert", "-O", "qcow2", str(cloud_image), str(work)], check=True)
    subprocess.run([qemu_img, "resize", "-q", str(work), DISK_SIZE], check=True)

    print("4/5 First boot with cloud-init (installs packages; a few minutes)")
    chosen = accel.detect(force_software=args.software)
    print(f"  accelerator: {chosen.name}")
    server, http_port = serve_cloud_init(root_pub, player_pub)
    serial_log = config.IMAGES_OUT / "build-serial.log"
    spec = qemu.VMSpec(
        disk=work,
        accel=chosen,
        ssh_port=qemu.free_port(),   # unused during the build, but harmless
        serial_log=serial_log,
        smbios_serial=f"ds=nocloud;s=http://10.0.2.2:{http_port}/",
    )
    started = time.monotonic()
    timeout = 20 * 60 if chosen.hardware else 120 * 60
    try:
        proc = subprocess.run(qemu.command(spec), timeout=timeout)
    except subprocess.TimeoutExpired:
        sys.exit(f"VM did not power off within {timeout // 60} min; see {serial_log}")
    finally:
        server.shutdown()
    print(f"  VM powered off after {time.monotonic() - started:.0f}s (exit {proc.returncode})")

    print("5/5 Checking result")
    log = serial_log.read_text(errors="replace")
    if SUCCESS_MARKER not in log:
        sys.exit(f"Build marker missing. cloud-init probably failed; see {serial_log}")
    work.replace(config.BASE_IMAGE)
    print(f"Done: {config.BASE_IMAGE}")


if __name__ == "__main__":
    main()
