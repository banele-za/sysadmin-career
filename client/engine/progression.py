"""Which tickets the player may get next: the career ladder.

Two rules decide whether a ticket is unlocked:

  1. Tiers in order. Every ticket of a lower tier must be solved first
     (Help Desk before Sysadmin). Real promotions with XP thresholds and
     mastery come later; this is the simple version.
  2. Skills in order. Within one skill (say "permissions"), a ticket needs
     every lower-level ticket solved, and at the same level the guided
     tutorial comes before the unguided ones. That's the design doc's
     "guided, then unguided" pattern.

`tickets.load_all` already sorts tickets in ladder order (see
tickets.ladder_key): within a tier, skill by skill in the order of
content/chapters.yaml. So "the next ticket" is simply the first unlocked
one that isn't solved yet, and the player finishes one skill's tutorial
and practice before the next skill begins.
"""

from dataclasses import dataclass

from client.engine.tickets import Ticket

TIER_NAMES = {1: "Help Desk", 2: "Sysadmin", 3: "Sys Engineer"}


def _comes_before(a: Ticket, b: Ticket) -> bool:
    """True if `a` must be solved before `b` is unlocked."""
    if a.tier < b.tier:
        return True
    same_skill = a.skill == b.skill and a.id != b.id
    return same_skill and (a.level, not a.guided) < (b.level, not b.guided)


def is_unlocked(ticket: Ticket, all_tickets: list[Ticket], solved: set[str]) -> bool:
    return all(other.id in solved for other in all_tickets if _comes_before(other, ticket))


def pick_next(all_tickets: list[Ticket], solved: set[str], current_id: str | None = None) -> Ticket:
    """The first unlocked, unsolved ticket; if none is left, a repeat.

    Repeats rotate through the unlocked tickets so the same one doesn't come
    up twice in a row.
    """
    unlocked = [t for t in all_tickets if is_unlocked(t, all_tickets, solved)]
    for t in unlocked:
        if t.id not in solved:
            return t
    ids = [t.id for t in unlocked]
    if current_id in ids:
        return unlocked[(ids.index(current_id) + 1) % len(unlocked)]
    return unlocked[0]


@dataclass
class Progress:
    tier: int
    tier_name: str
    solved: int        # tickets solved in this tier
    total: int         # tickets in this tier


def progress(all_tickets: list[Ticket], solved: set[str]) -> Progress:
    """The player's current tier: the lowest one with unsolved tickets."""
    tiers = sorted({t.tier for t in all_tickets})
    current = next((tier for tier in tiers
                    if any(t.id not in solved for t in all_tickets if t.tier == tier)),
                   tiers[-1])
    in_tier = [t for t in all_tickets if t.tier == current]
    return Progress(
        tier=current,
        tier_name=TIER_NAMES.get(current, f"Tier {current}"),
        solved=sum(t.id in solved for t in in_tier),
        total=len(in_tier),
    )
