# PyInstaller recipe for the Linux game folder. Run it through build.py,
# which writes build/VERSION first and then wraps the folder in an AppImage.
#
# Same layout as the Windows build (see packaging/windows/), except:
#   - no QEMU inside: Linux uses the distribution's QEMU package, which the
#     checkup offers to install;
#   - the Qt web view is inside (see host.WEBVIEW_GUI for why).

import re
from pathlib import Path

REPO = Path(SPECPATH).parents[1]

# Libraries we must NOT ship, but take from the player's system instead.
#
# The player's graphics driver (e.g. Mesa) is loaded into the game's process
# and needs these libraries in versions at least as new as its own. If the
# bundle carries older copies from the build machine (Ubuntu 22.04), those
# win, the driver fails to load, and Qt dies with "Could not initialize GLX".
# Every desktop Linux has them, in the same or newer versions than 22.04
# (builds run on the oldest supported system for exactly this reason).
# The less common X helpers (libxcb-cursor, -icccm, -image, -keysyms,
# -render-util, -util) stay inside, since many systems lack them.
FROM_THE_SYSTEM = re.compile(
    r"^lib("
    r"GL|EGL|GLX|GLdispatch|OpenGL|gbm|drm|drm_\w+"           # graphics drivers
    r"|X11|X11-xcb|Xau|Xdmcp|Xext|xshmfence|xcb"               # talking to the X server
    r"|xcb-(glx|randr|render|shape|shm|sync|xfixes|xkb|dri2|dri3|present)"
    r"|wayland-(client|server|egl|cursor)"
    r"|stdc\+\+|gcc_s|z|zstd|lzma|expat|ffi|bsd|md|tinfo"     # basics the driver links to
    r"|elf|sensors|xml2|edit"
    r"|fontconfig|freetype|asound|glib-2\.0|gobject-2\.0|gio-2\.0|gthread-2\.0"
    r")\.so")

datas = [
    (str(REPO / "client" / "ui"), "client/ui"),
    (str(REPO / "content"), "content"),
    (str(REPO / "guides"), "guides"),
    (str(REPO / "packaging" / "icons" / "icon.png"), "packaging/icons"),
    (str(REPO / "build" / "VERSION"), "."),
    (str(REPO / "LICENSE"), "."),
    (str(REPO / "LICENSE-CONTENT"), "."),
    (str(REPO / "THIRD-PARTY.md"), "."),
]

a = Analysis(
    [str(REPO / "packaging" / "launch.py")],
    pathex=[str(REPO)],
    datas=datas,
    hiddenimports=["webview.platforms.qt"],
    # pywebview's other Linux backend, and things we never use.
    excludes=["pytest", "tkinter", "gi", "webview.platforms.gtk"],
)
pyz = PYZ(a.pure)

# a.binaries entries are (name inside the folder, source path, kind).
binaries = [b for b in a.binaries if not FROM_THE_SYSTEM.match(Path(b[0]).name)]
print(f"leaving {len(a.binaries) - len(binaries)} system libraries out of the bundle")

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="sysadmin-career")

coll = COLLECT(exe, binaries, a.datas, name="sysadmin-career")
