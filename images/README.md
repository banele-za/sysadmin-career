# Base images

`build_rhel.py` builds the Red Hat track image from the official AlmaLinux 10
GenericCloud image (x86_64_v2 build, so it also runs on older CPUs and in
software emulation).

```
.venv\Scripts\python images\build_rhel.py          # uses WHPX/KVM/HVF if available
.venv\Scripts\python images\build_rhel.py --software
```

Outputs (git-ignored):

| Path | What |
| --- | --- |
| `images/cache/` | the downloaded cloud image (checksum-verified, reused) |
| `images/out/alma10-base.qcow2` | the finished base image |
| `images/out/keys/game_root` | private key the game uses to run break/grade as root |
| `images/out/keys/player` | private key for the player's terminal (user `admin`) |
| `images/out/build-serial.log` | the VM console during the build, for debugging |

What the build changes inside the image is all in `cloud-init/user-data`.
To update the OS, bump `IMAGE_NAME` and `IMAGE_SHA256` in `build_rhel.py`
(values from the `CHECKSUM` file next to the images on repo.almalinux.org).

**Reproducibility:** the same pinned cloud image and user-data give the same
system, except for the packages installed with `dnf`, which come from the
live AlmaLinux mirrors at build time and may be newer on a later build.
The SSH keys are generated once per checkout and reused on rebuilds.

**Note for release:** every copy of a built image trusts the same two keys,
and the client ships the private halves. That's fine for a VM reachable only
on 127.0.0.1, but it's a deliberate trade-off worth revisiting before release.
