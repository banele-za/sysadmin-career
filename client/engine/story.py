"""Story pages: the first-day intro and the promotion scenes.

The text lives in content/story/ (intro.yaml, promotions.yaml), so writers
never touch Python. Names that may change, like the company's, live once in
world.yaml and appear in the text as {company} or {server}.
"""

import yaml

from client import config

STORY_DIR = config.CONTENT_DIR / "story"


def _load(name: str):
    return yaml.safe_load((STORY_DIR / name).read_text(encoding="utf-8")) or {}


def _fill(pages: list[dict], world: dict) -> list[dict]:
    """Fill {company}/{server} into each page's title and text."""
    return [{"title": p["title"].format(**world), "text": p["text"].strip().format(**world)}
            for p in pages]


def intro() -> list[dict]:
    return _fill(_load("intro.yaml")["pages"], _load("world.yaml"))


def promotion(new_tier: int) -> list[dict]:
    """The scene for reaching `new_tier`, or [] if there isn't one."""
    return _fill(_load("promotions.yaml").get(new_tier, []), _load("world.yaml"))
