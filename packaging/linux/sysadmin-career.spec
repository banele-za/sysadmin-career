# PyInstaller recipe for the Linux game folder. Run it through build.py,
# which writes build/VERSION first and then wraps the folder in an AppImage.
#
# Same layout as the Windows build (see packaging/windows/), except:
#   - no QEMU inside: Linux uses the distribution's QEMU package, which the
#     checkup offers to install;
#   - the Qt web view is inside (see host.WEBVIEW_GUI for why).

from pathlib import Path

REPO = Path(SPECPATH).parents[1]

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

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="sysadmin-career")

coll = COLLECT(exe, a.binaries, a.datas, name="sysadmin-career")
