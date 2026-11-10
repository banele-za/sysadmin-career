from client import config
from client.engine import economy, tickets
from client.save.db import SaveFile


def test_solve_adds_rewards_and_persists(tmp_path):
    path = tmp_path / "save.db"
    save = SaveFile(path)
    attempt = save.start_attempt("perm-03-setgid-shared", 7, {"group": "audit"})
    save.record_submit(attempt)
    p = save.solve(attempt, xp=40, rep=15)
    assert (p.xp, p.rep) == (40, 15)
    save.close()

    reopened = SaveFile(path)          # a new session sees the same progress
    assert reopened.player().xp == 40
    assert reopened.solved_ticket_ids() == {"perm-03-setgid-shared"}
    reopened.close()


def test_repeat_solves_pay_less():
    ticket = next(t for t in tickets.load_all(config.TICKETS_DIR) if t.id == "perm-03-setgid-shared")
    assert economy.reward_for(ticket, already_solved=False) == economy.Reward(40, 15)
    assert economy.reward_for(ticket, already_solved=True) == economy.Reward(10, 3)


def test_settings_roundtrip(tmp_path):
    save = SaveFile(tmp_path / "save.db")
    assert save.get_setting("slow_mode_accepted", False) is False
    save.set_setting("slow_mode_accepted", True)
    save.close()
    assert SaveFile(tmp_path / "save.db").get_setting("slow_mode_accepted") is True


def test_version_1_save_is_migrated(tmp_path):
    """A save from Milestone 1 (schema v1, no settings table) keeps its progress."""
    import sqlite3
    from client.save import db as db_mod
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(db_mod.SCHEMA)
    old.execute("INSERT INTO player (id, track, xp, rep, created_at) VALUES (1, 'rhel', 60, 20, 0)")
    old.execute("PRAGMA user_version = 1")
    old.commit()
    old.close()

    save = SaveFile(path)
    assert save.player().xp == 60
    save.set_setting("checkup_seen", True)                 # the new table exists
    assert save.db.execute("PRAGMA user_version").fetchone()[0] == db_mod.SCHEMA_VERSION
    assert save.hints_used(save.start_attempt("x", 1, {})) == 0   # ... and the v3 columns


def test_hints_are_counted_per_attempt(tmp_path):
    save = SaveFile(tmp_path / "save.db")
    first = save.start_attempt("perm-01-chmod", 1, {})
    assert save.record_hint(first) == 1
    assert save.record_hint(first) == 2
    assert save.hints_used(save.start_attempt("perm-01-chmod", 2, {})) == 0   # a new attempt starts clean
    save.solve(first, xp=25, rep=4, used_man=True)
    row = save.db.execute("SELECT hints_used, used_man FROM attempts WHERE id = ?", (first,)).fetchone()
    assert (row["hints_used"], row["used_man"]) == (2, 1)


# ---- hints and the man-page bonus (engine/economy.py) ----------------------------

def test_hints_are_paid_from_the_ticket_reward():
    ticket = next(t for t in tickets.load_all(config.TICKETS_DIR) if t.id == "perm-03-setgid-shared")
    rep = [economy.reward_for(ticket, False, hints_used=n).rep for n in range(4)]
    assert rep == [15, 11, 8, 0]                     # 100%, 75%, 50%, 0% of 15 (rounded)
    costs = [economy.next_hint_cost(ticket, False, n) for n in range(3)]
    assert costs == [4, 3, 8] and sum(costs) == 15   # the three prices add up to the whole reward
    assert economy.reward_for(ticket, False, hints_used=3).xp == 40   # XP is never taken away


def test_man_bonus_only_on_the_first_solve():
    ticket = next(t for t in tickets.load_all(config.TICKETS_DIR) if t.id == "perm-03-setgid-shared")
    first = economy.reward_for(ticket, already_solved=False, used_man=True)
    assert (first.xp, first.man_bonus) == (40 + economy.MAN_BONUS_XP, economy.MAN_BONUS_XP)
    assert economy.reward_for(ticket, already_solved=True, used_man=True).man_bonus == 0
