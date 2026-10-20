"""XP and reputation rewards.

Milestone 1 keeps this deliberately simple: a ticket pays its full
`rewards` the first time it's solved, and a quarter (rounded down) on
repeats. Real tuning (hint costs, mastery, decay) comes in M5.
"""

from client.engine.tickets import Ticket

REPEAT_FACTOR = 0.25


def reward_for(ticket: Ticket, already_solved: bool) -> tuple[int, int]:
    """(xp, rep) for solving `ticket` now."""
    xp, rep = ticket.rewards["xp"], ticket.rewards["rep"]
    if already_solved:
        return int(xp * REPEAT_FACTOR), int(rep * REPEAT_FACTOR)
    return xp, rep
