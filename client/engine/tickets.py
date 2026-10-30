"""Load ticket folders from content/tickets/.

A ticket is a folder containing ticket.yaml plus Bash scripts:

    content/tickets/<tier>/<id>/
        ticket.yaml     metadata, params, story text (see docs/DESIGN.md)
        break.sh        puts the VM into the broken state (runs as root)
        grade.sh        checks the end state, prints JSON lines (runs as root)
        solution.sh     optional: a reference fix, used only by tests

Track-specific versions (break.rhel.sh, grade.suse.sh, ...) win over the
generic ones when present.

Adding a ticket never needs Python changes: drop in a folder and it's loaded.
"""

import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from client.engine import params as params_mod

REQUIRED_KEYS = ["id", "title", "tier", "skill", "character", "tracks", "narrative", "rewards"]


class TicketError(ValueError):
    pass


@dataclass
class MentorStep:
    say: str                 # what the mentor writes in the chat panel
    check: str | None = None # Bash run as root; exit 0 means "player did this step"


@dataclass
class Ticket:
    id: str
    title: str
    tier: int
    skill: str
    level: int
    objectives: list[str]
    character: str
    tracks: list[str]
    params: dict
    narrative: str
    mentor_steps: list[MentorStep]
    mentor_intro: str | None        # one mentor message for an unguided ticket
    hints: list[str]
    requires_reboot: bool
    time_limit: int | None
    rewards: dict
    folder: Path

    @property
    def guided(self) -> bool:
        return bool(self.mentor_steps)

    def script(self, name: str, track: str) -> str | None:
        """Text of e.g. break.sh, preferring break.<track>.sh if it exists."""
        for candidate in (f"{name}.{track}.sh", f"{name}.sh"):
            path = self.folder / candidate
            if path.exists():
                # Normalise Windows line endings: Bash chokes on "\r".
                return path.read_text(encoding="utf-8").replace("\r\n", "\n")
        return None


@dataclass
class TicketInstance:
    """A ticket with its params rolled: what the player actually works on."""
    ticket: Ticket
    seed: int
    values: dict = field(default_factory=dict)

    @property
    def env(self) -> dict[str, str]:
        return params_mod.to_env(self.values)

    def text(self, template: str) -> str:
        return params_mod.render(template, self.values)

    @property
    def narrative(self) -> str:
        return self.text(self.ticket.narrative).strip()


def load_ticket(yaml_path: Path) -> Ticket:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise TicketError(f"{yaml_path}: missing keys {missing}")
    folder = yaml_path.parent
    if folder.name != data["id"]:
        raise TicketError(f"{yaml_path}: folder name must match id '{data['id']}'")
    for script in ("break", "grade"):
        if not any(folder.glob(f"{script}*.sh")):
            raise TicketError(f"{yaml_path}: no {script}.sh")

    steps = [MentorStep(say=s["say"], check=s.get("check")) for s in data.get("mentor_steps") or []]
    return Ticket(
        id=data["id"],
        title=data["title"],
        tier=int(data["tier"]),
        skill=data["skill"],
        level=int(data.get("level", 1)),
        objectives=list(data.get("objectives") or []),
        character=data["character"],
        tracks=list(data["tracks"]),
        params=data.get("params") or {},
        narrative=data["narrative"],
        mentor_steps=steps,
        mentor_intro=data.get("mentor_intro"),
        hints=list(data.get("hints") or []),
        requires_reboot=bool(data.get("requires_reboot", False)),
        time_limit=data.get("time_limit"),
        rewards={"xp": int(data["rewards"].get("xp", 0)), "rep": int(data["rewards"].get("rep", 0))},
        folder=folder,
    )


def ladder_key(t: Ticket) -> tuple:
    """The order the player meets tickets in: tier, then level, guided
    tutorial before unguided practice, then id. See engine/progression.py."""
    return (t.tier, t.level, not t.guided, t.id)


def load_all(root: Path, track: str | None = None) -> list[Ticket]:
    """Every ticket under `root` in ladder order, optionally for one track."""
    tickets = [load_ticket(p) for p in root.rglob("ticket.yaml")]
    ids = [t.id for t in tickets]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise TicketError(f"duplicate ticket ids: {sorted(duplicates)}")
    if track:
        tickets = [t for t in tickets if track in t.tracks]
    return sorted(tickets, key=ladder_key)


def instantiate(ticket: Ticket, seed: int | None = None) -> TicketInstance:
    """Roll the ticket's params. Pass a seed to reproduce an earlier roll."""
    if seed is None:
        seed = random.randrange(2**31)
    return TicketInstance(ticket, seed, params_mod.resolve(ticket.params, seed))
