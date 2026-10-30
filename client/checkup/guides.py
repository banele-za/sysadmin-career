"""The picture-guided BIOS instructions.

guides/<brand>.yaml holds what differs between PC makers (keys, menu paths);
the steps themselves are written once, here. Every step reassures the
player, and the UI always offers "Skip, play in slow mode".
"""

import re
from pathlib import Path

import yaml

from client import config

GUIDES_DIR = config.REPO_ROOT / "guides"

SETTING_NAMES = {
    "intel": "Intel Virtualization Technology (also called VT-x)",
    "amd": "SVM Mode (also called AMD-V)",
    "": "Virtualization Technology (Intel VT-x, or SVM / AMD-V on AMD)",
}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def find_guide(manufacturer: str) -> dict:
    """The guide whose `match` words appear in the maker's name, else generic."""
    name = manufacturer.lower()
    for path in sorted(GUIDES_DIR.glob("*.yaml")):
        guide = _load(path)
        # Whole words only, so "hp" doesn't match a name that merely contains it.
        if any(re.search(rf"\b{re.escape(word)}\b", name) for word in guide.get("match") or []):
            return guide
    return _load(GUIDES_DIR / "generic.yaml")


def build(manufacturer: str, cpu_vendor: str) -> dict:
    """Everything the UI needs to show the guide for this PC."""
    guide = find_guide(manufacturer)
    setting = SETTING_NAMES.get(cpu_vendor, SETTING_NAMES[""])
    menu = guide["menus"].get(cpu_vendor) or " or ".join(guide["menus"].values())
    keys = " or ".join(guide["keys"])
    steps = [
        {
            "title": "Don't worry, this is a normal setting",
            "text": ("Your computer has a built-in speed boost for running other systems, "
                     "and it's switched off. Turning it on is safe and doesn't touch your "
                     "files. It takes about five minutes."),
        },
        {
            "title": "Open the BIOS",
            "text": ("Save anything you're working on, then click \"Restart into BIOS\" "
                     "below. If that doesn't work, restart normally and tap "
                     f"{keys} as soon as the screen lights up."),
            "screen": f"{guide['brand'].upper()} SETUP UTILITY\n\nPress {keys} to enter setup",
        },
        {
            "title": f"Find \"{setting}\"",
            "text": ("Use the arrow keys to move around (the mouse may not work). "
                     "On most PCs like yours it's here:"),
            "screen": menu.replace("  >  ", "\n  > ") + "      [Disabled]",
        },
        {
            "title": "Switch it to Enabled",
            "text": "Select the setting, press Enter, and choose Enabled.",
            "screen": setting.split(" (")[0] + "      [Enabled]",
        },
        {
            "title": "Save and restart",
            "text": ("Press F10 (or find \"Save & Exit\") and confirm with Yes. Your PC "
                     "restarts normally. Open the game again and it checks everything "
                     "by itself."),
            "screen": "Save configuration and exit?\n\n      [Yes]      No",
        },
    ]
    return {
        "brand": guide["brand"],
        "setting": setting,
        "steps": steps,
        "notes": guide.get("notes") or [],
        "placeholder": True,     # art and menu paths still need checking on real PCs
    }
