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
    assert economy.reward_for(ticket, already_solved=False) == (40, 15)
    assert economy.reward_for(ticket, already_solved=True) == (10, 3)
