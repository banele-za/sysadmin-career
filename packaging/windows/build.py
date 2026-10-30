"""Build the Windows installer: dist/SysadminCareer-Setup-<version>.exe

    .venv\\Scripts\\pip install -r requirements-build.txt
    winget install JRSoftware.InnoSetup
    .venv\\Scripts\\python packaging\\windows\\build.py

Three stages:
  1. vendor/qemu   - the trimmed copy of QEMU (vendor_qemu.py), unless present
  2. PyInstaller   - Python + the game + its files -> dist/SysadminCareer/
  3. Inno Setup    - that folder -> one Setup.exe with Start-menu entry and uninstaller

The version is `git describe` (e.g. "b2dcf95", or "v0.3.0" once tags exist),
written to build/VERSION so the diagnostic report can show it.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import vendor_qemu      # noqa: E402  (needs the path above)


def git_version() -> str:
    # Only game version tags (v0.3.0) count, not the image releases (image-v1).
    out = subprocess.run(["git", "-C", str(REPO), "describe", "--tags", "--match", "v*",
                          "--always", "--dirty"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def find_iscc() -> Path:
    for folder in (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6",
                   Path(r"C:\Program Files (x86)\Inno Setup 6")):
        if (folder / "ISCC.exe").exists():
            return folder / "ISCC.exe"
    sys.exit("Inno Setup not found: winget install JRSoftware.InnoSetup")


def main() -> None:
    if not (REPO / "vendor" / "qemu" / "qemu-system-x86_64.exe").exists():
        vendor_qemu.vendor(Path(r"C:\Program Files\qemu"))

    version = git_version()
    print(f"building version {version}")
    (REPO / "build").mkdir(exist_ok=True)
    (REPO / "build" / "VERSION").write_text(version + "\n", encoding="utf-8")

    shutil.rmtree(REPO / "dist" / "SysadminCareer", ignore_errors=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--log-level", "WARN",
                    "--workpath", str(REPO / "build" / "pyinstaller"),
                    "--distpath", str(REPO / "dist"),
                    str(HERE / "sysadmin-career.spec")], check=True)

    subprocess.run([str(find_iscc()), "/Q", f"/DGameVersion={version}",
                    str(HERE / "installer.iss")], check=True)
    setup = REPO / "dist" / f"SysadminCareer-Setup-{version}.exe"
    print(f"done: {setup} ({setup.stat().st_size / 2**20:.0f} MB)")


if __name__ == "__main__":
    main()
