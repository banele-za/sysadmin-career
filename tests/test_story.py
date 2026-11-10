"""Story text: the files load, and every {placeholder} gets filled."""

import yaml

from client import config
from client.engine import story, tickets


def test_intro_and_promotion_fill_the_world_names():
    world = yaml.safe_load((config.CONTENT_DIR / "story" / "world.yaml").read_text())
    pages = story.intro() + story.promotion(2)
    assert pages and all(p["title"] and p["text"] for p in pages)
    text = " ".join(p["title"] + p["text"] for p in pages)
    assert "{" not in text and world["company"] in text


def test_no_promotion_scene_means_none_shown():
    assert story.promotion(99) == []


def test_every_ticket_sender_is_in_the_cast():
    cast = yaml.safe_load((config.CONTENT_DIR / "characters" / "cast.yaml").read_text())
    for t in tickets.load_all(config.TICKETS_DIR):
        assert t.character in cast, f"{t.id}: unknown character {t.character!r}"
        assert {"name", "role", "initials", "color"} <= cast[t.character].keys()
