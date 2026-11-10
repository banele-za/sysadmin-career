"""The career ladder: unlock rules, and a lint that keeps real content in order."""

from collections import defaultdict
from pathlib import Path

import pytest

from client import config
from client.engine import progression, tickets


def make(id, tier=1, skill="perms", level=1, guided=False) -> tickets.Ticket:
    steps = [tickets.MentorStep(say="hi")] if guided else []
    return tickets.Ticket(
        id=id, title=id, tier=tier, skill=skill, level=level, objectives=[], character="c",
        tracks=["rhel"], params={}, narrative="", mentor_steps=steps, mentor_intro=None,
        callback=None, hints=[], requires_reboot=False, time_limit=None, rewards={"xp": 1, "rep": 1},
        folder=Path("."),
    )


LADDER = sorted([
    make("files-tut", skill="files", guided=True),
    make("perm-tut", guided=True),
    make("perm-1"),
    make("perm-2", level=2),
    make("perm-3", tier=2, level=3),
], key=tickets.ladder_key)


def test_ladder_order():
    assert [t.id for t in LADDER] == ["files-tut", "perm-tut", "perm-1", "perm-2", "perm-3"]


def test_guided_comes_before_unguided():
    # Solving the files tutorial doesn't let you skip the permissions one.
    assert not progression.is_unlocked(LADDER[2], LADDER, {"files-tut"})
    assert progression.is_unlocked(LADDER[2], LADDER, {"perm-tut"})


def test_level_2_needs_level_1():
    assert not progression.is_unlocked(LADDER[3], LADDER, {"perm-tut"})
    assert progression.is_unlocked(LADDER[3], LADDER, {"perm-tut", "perm-1"})


def test_next_tier_needs_whole_tier():
    tier1_but_one = {"perm-tut", "perm-1", "perm-2"}
    assert not progression.is_unlocked(LADDER[4], LADDER, tier1_but_one)
    assert progression.is_unlocked(LADDER[4], LADDER, tier1_but_one | {"files-tut"})


def test_pick_walks_the_ladder():
    solved: set[str] = set()
    order = []
    for _ in LADDER:
        t = progression.pick_next(LADDER, solved)
        order.append(t.id)
        solved.add(t.id)
    assert order == [t.id for t in LADDER]


def test_repeats_rotate_when_all_solved():
    solved = {t.id for t in LADDER}
    assert progression.pick_next(LADDER, solved, current_id="perm-2").id == "perm-3"
    assert progression.pick_next(LADDER, solved, current_id="perm-3").id == "files-tut"


def test_progress_counts_current_tier():
    p = progression.progress(LADDER, {"files-tut", "perm-tut"})
    assert (p.tier_name, p.solved, p.total) == ("Help Desk", 2, 4)
    p = progression.progress(LADDER, {"files-tut", "perm-tut", "perm-1", "perm-2"})
    assert (p.tier_name, p.solved, p.total) == ("Sysadmin", 0, 1)


def write_ticket(root: Path, id: str, skill: str, guided: bool = False) -> None:
    """A minimal ticket folder on disk (yaml + empty scripts)."""
    folder = root / "tickets" / id
    folder.mkdir(parents=True)
    steps = "mentor_steps: [{say: hi}]\n" if guided else ""
    (folder / "ticket.yaml").write_text(
        f"id: {id}\ntitle: t\ntier: 1\nskill: {skill}\ncharacter: c\ntracks: [rhel]\n"
        f"narrative: n\nrewards: {{xp: 1, rep: 1}}\n{steps}")
    for script in ("break.sh", "grade.sh"):
        (folder / script).write_text("")


def test_chapters_keep_each_tutorial_next_to_its_practice(tmp_path):
    # Two skills, each a tutorial plus a practice ticket. Without chapters the
    # sort is by level, so both tutorials would come first.
    (tmp_path / "chapters.yaml").write_text("1: [files, perms]\n")
    write_ticket(tmp_path, "files-tut", "files", guided=True)
    write_ticket(tmp_path, "files-1", "files")
    write_ticket(tmp_path, "perm-tut", "perms", guided=True)
    write_ticket(tmp_path, "perm-1", "perms")
    order = [t.id for t in tickets.load_all(tmp_path / "tickets")]
    assert order == ["files-tut", "files-1", "perm-tut", "perm-1"]


def test_unknown_chapter_is_refused(tmp_path):
    (tmp_path / "chapters.yaml").write_text("1: [files]\n")
    write_ticket(tmp_path, "x", "fiels")
    with pytest.raises(tickets.TicketError, match="fiels"):
        tickets.load_all(tmp_path / "tickets")


# ---- lint the real content -------------------------------------------------

def test_real_content_climbs_gently():
    """Every skill starts with a guided ticket at level 1, levels have no gaps,
    and a higher level never sits in a lower tier. This stops a new ticket
    from throwing beginners into the deep end."""
    by_skill = defaultdict(list)
    for t in tickets.load_all(config.TICKETS_DIR, track="rhel"):
        by_skill[t.skill].append(t)
    for skill, ts in by_skill.items():
        first = min(ts, key=tickets.ladder_key)
        assert first.level == 1 and first.guided, f"{skill}: must start with a guided level-1 ticket"
        levels = sorted({t.level for t in ts})
        assert levels == list(range(1, levels[-1] + 1)), f"{skill}: levels skip a step: {levels}"
        for a in ts:
            for b in ts:
                assert not (a.level < b.level and a.tier > b.tier), \
                    f"{skill}: {a.id} (level {a.level}) is in a later tier than {b.id}"


def test_whole_real_ladder_is_reachable():
    real = tickets.load_all(config.TICKETS_DIR, track="rhel")
    solved: set[str] = set()
    for _ in real:
        solved.add(progression.pick_next(real, solved).id)
    assert solved == {t.id for t in real}
