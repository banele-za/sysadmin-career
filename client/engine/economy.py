"""XP and reputation rewards.

Still deliberately simple (real tuning comes with M5's mastery system):

  - A ticket pays its full `rewards` the first time it's solved, and a
    quarter (rounded down) on repeats.
  - Hints are paid out of the ticket's own reputation reward, so a brand-new
    player with 0 rep can still ask for one: after 1, 2 or 3 hints the
    ticket pays 75%, 50% or 0% of its rep. XP stays: you still learned it.
  - Reading a man page during a ticket earns a small XP bonus the first time
    that ticket is solved (the design doc's "man pages first").
"""

from dataclasses import dataclass

from client.engine.tickets import Ticket

REPEAT_FACTOR = 0.25
# Share of the ticket's rep reward given up after 0, 1, 2, 3 hints.
HINT_REP_LOSS = [0.0, 0.25, 0.5, 1.0]
MAN_BONUS_XP = 5


@dataclass
class Reward:
    xp: int              # includes man_bonus
    rep: int
    man_bonus: int = 0   # the part of xp earned by reading the manual


def _base(ticket: Ticket, already_solved: bool) -> tuple[int, int]:
    xp, rep = ticket.rewards["xp"], ticket.rewards["rep"]
    if already_solved:
        return int(xp * REPEAT_FACTOR), int(rep * REPEAT_FACTOR)
    return xp, rep


def _rep_after_hints(rep: int, hints_used: int) -> int:
    loss = HINT_REP_LOSS[min(hints_used, len(HINT_REP_LOSS) - 1)]
    return round(rep * (1 - loss))


def reward_for(ticket: Ticket, already_solved: bool, hints_used: int = 0,
               used_man: bool = False) -> Reward:
    """What solving `ticket` pays right now."""
    xp, rep = _base(ticket, already_solved)
    bonus = MAN_BONUS_XP if used_man and not already_solved else 0
    return Reward(xp=xp + bonus, rep=_rep_after_hints(rep, hints_used), man_bonus=bonus)


def next_hint_cost(ticket: Ticket, already_solved: bool, hints_used: int) -> int:
    """How much rep the next hint takes off this ticket's reward."""
    _, rep = _base(ticket, already_solved)
    return _rep_after_hints(rep, hints_used) - _rep_after_hints(rep, hints_used + 1)
