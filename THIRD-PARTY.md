# Third-party software

Sysadmin Career is built on other people's open-source work. This file lists
what the game includes or downloads, under which licence, and where the
source code is. Each package's full licence text ships with it (Python
packages keep theirs in their `*.dist-info` folder; xterm.js's are in
`client/ui/vendor/xterm/`).

## Shipped with the game

| Component | Used for | Licence | Source |
| --- | --- | --- | --- |
| [Python](https://www.python.org/) | runs the game | PSF-2.0 | https://github.com/python/cpython |
| [xterm.js](https://xtermjs.org/) + addon-fit | the terminal | MIT | https://github.com/xtermjs/xterm.js |
| [pywebview](https://pywebview.flowrl.com/) | the game window | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| bottle, proxy_tools | pywebview helpers | MIT | https://github.com/bottlepy/bottle, https://github.com/jtushman/proxy_tools |
| pythonnet, clr_loader | pywebview on Windows | MIT | https://github.com/pythonnet/pythonnet, https://github.com/pythonnet/clr-loader |
| [AsyncSSH](https://github.com/ronf/asyncssh) | SSH connection to the VM | EPL-2.0 or GPL-2.0-or-later (used under the GPL) | https://github.com/ronf/asyncssh |
| cryptography (includes OpenSSL) | AsyncSSH's encryption | Apache-2.0 or BSD-3-Clause; OpenSSL: Apache-2.0 | https://github.com/pyca/cryptography |
| cffi, pycparser | cryptography helpers | MIT-0, BSD-3-Clause | https://github.com/python-cffi/cffi, https://github.com/eliben/pycparser |
| typing_extensions | Python compatibility | PSF-2.0 | https://github.com/python/typing_extensions |
| [PyYAML](https://pyyaml.org/) | reads ticket files | MIT | https://github.com/yaml/pyyaml |
| [QEMU](https://www.qemu.org/) (Windows builds only) | runs the hidden Linux VM | GPL-2.0 | https://download.qemu.org/ (the exact version is in `vendor/qemu/VERSION`) |

QEMU is a separate program: the game starts it and talks to it over a local
network socket, it isn't built into the game's own code. On Linux the game
uses the QEMU package from your distribution instead of shipping one.

The Windows WebView2 runtime that draws the game window is part of Windows
and isn't shipped with the game.

## Downloaded on first launch

| Component | Licence | Source |
| --- | --- | --- |
| The Linux server image, built from the official [AlmaLinux](https://almalinux.org/) 10 cloud image by `images/build_rhel.py` | Mostly GPL and other open-source licences; each package's licence is inside the image under `/usr/share/licenses/` | https://vault.almalinux.org/ (source packages) and https://git.almalinux.org/ |

The image is AlmaLinux with a few extra packages and settings (see
`images/cloud-init/user-data`). It isn't an official AlmaLinux release.
AlmaLinux is a trademark of the AlmaLinux OS Foundation.

## Used only for development

pytest, pluggy, iniconfig, packaging, Pygments, colorama: test tools, not
shipped with the game.
