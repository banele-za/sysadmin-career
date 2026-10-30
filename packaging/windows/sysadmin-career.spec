# PyInstaller recipe for the Windows game folder. Run it through build.py,
# which prepares vendor/qemu and build/VERSION first.
#
# Result: dist/SysadminCareer/
#   SysadminCareer.exe        the game (no console window)
#   _internal/                Python, the libraries, and our files laid out
#                             like the repo, so client/config.py's paths work:
#     client/ui/ content/ guides/ vendor/qemu/ VERSION LICENSE ...

from pathlib import Path

REPO = Path(SPECPATH).parents[1]          # SPECPATH: the folder this file is in

# (source on disk, folder inside _internal)
datas = [
    (str(REPO / "client" / "ui"), "client/ui"),
    (str(REPO / "content"), "content"),
    (str(REPO / "guides"), "guides"),
    (str(REPO / "vendor" / "qemu"), "vendor/qemu"),
    (str(REPO / "build" / "VERSION"), "."),
    (str(REPO / "LICENSE"), "."),
    (str(REPO / "LICENSE-CONTENT"), "."),
    (str(REPO / "THIRD-PARTY.md"), "."),
]

a = Analysis(
    [str(REPO / "packaging" / "launch.py")],
    pathex=[str(REPO)],                    # so `import client` works
    datas=datas,
    # pywebview picks its Windows backend at runtime; name it so it's included.
    hiddenimports=["webview.platforms.edgechromium", "webview.platforms.winforms"],
    excludes=["pytest", "tkinter"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SysadminCareer",
    console=False,                         # a game window, not a terminal
    icon=str(REPO / "packaging" / "icons" / "icon.ico"),
)

coll = COLLECT(exe, a.binaries, a.datas, name="SysadminCareer")
