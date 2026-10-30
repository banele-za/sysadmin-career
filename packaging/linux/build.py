"""Build the Linux AppImage: dist/SysadminCareer-<version>-x86_64.AppImage

    ~/venv/bin/pip install -r requirements-build.txt
    ~/venv/bin/python packaging/linux/build.py

An AppImage is one executable file holding a small folder tree (the
"AppDir"). Running it mounts that tree and starts AppDir/AppRun. Ours:

    AppDir/
      AppRun                        starts the game (see AppRun for its one setting)
      sysadmin-career.desktop       name and icon for desktop menus
      sysadmin-career.png, .DirIcon the icon
      usr/lib/sysadmin-career/      what PyInstaller made: Python, Qt, the game

The AppImage runs on distributions at least as new as the one it was built
on (it uses that system's C library). Build releases on an older system,
e.g. Ubuntu 22.04, so more players can run it.
"""

import os
import shutil
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BUILD = REPO / "build"
DIST = REPO / "dist"

# appimagetool packs the AppDir into an AppImage. Its own releases are
# themselves AppImages; --appimage-extract-and-run lets it run without FUSE.
APPIMAGETOOL_URL = ("https://github.com/AppImage/appimagetool/releases/download/"
                    "continuous/appimagetool-x86_64.AppImage")


def git_version() -> str:
    out = subprocess.run(["git", "-C", str(REPO), "describe", "--tags", "--always", "--dirty"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def appimagetool() -> Path:
    tool = BUILD / "appimagetool-x86_64.AppImage"
    if not tool.exists():
        print("downloading appimagetool")
        urllib.request.urlretrieve(APPIMAGETOOL_URL, tool)
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return tool


def make_appdir(game_folder: Path) -> Path:
    appdir = BUILD / "AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(game_folder, appdir / "usr" / "lib" / "sysadmin-career", symlinks=True)
    shutil.copy2(HERE / "AppRun", appdir / "AppRun")
    (appdir / "AppRun").chmod(0o755)
    shutil.copy2(HERE / "sysadmin-career.desktop", appdir / "sysadmin-career.desktop")
    shutil.copy2(REPO / "packaging" / "icons" / "icon.png", appdir / "sysadmin-career.png")
    (appdir / ".DirIcon").symlink_to("sysadmin-career.png")
    return appdir


def main() -> None:
    version = git_version()
    print(f"building version {version}")
    BUILD.mkdir(exist_ok=True)
    (BUILD / "VERSION").write_text(version + "\n", encoding="utf-8")

    shutil.rmtree(DIST / "sysadmin-career", ignore_errors=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--log-level", "WARN",
                    "--workpath", str(BUILD / "pyinstaller"), "--distpath", str(DIST),
                    str(HERE / "sysadmin-career.spec")], check=True)

    appdir = make_appdir(DIST / "sysadmin-career")
    target = DIST / f"SysadminCareer-{version}-x86_64.AppImage"
    subprocess.run([str(appimagetool()), "--appimage-extract-and-run", "--no-appstream",
                    str(appdir), str(target)],
                   env={**os.environ, "ARCH": "x86_64"}, check=True)
    print(f"done: {target} ({target.stat().st_size / 2**20:.0f} MB)")


if __name__ == "__main__":
    main()
