"""The save file: a small SQLite database.

Tables:
  player   - one row: track, XP, reputation
  attempts - every ticket attempt: which ticket, its seed and params, outcome

Storing the seed means any attempt can be replayed with the same params.
`user_version` tracks the schema so later milestones can migrate old saves.
"""

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS player (
    id          INTEGER PRIMARY KEY CHECK (id = 1),   -- only ever one row
    track       TEXT    NOT NULL,
    xp          INTEGER NOT NULL DEFAULT 0,
    rep         INTEGER NOT NULL DEFAULT 0,
    created_at  REAL    NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY,
    ticket_id   TEXT    NOT NULL,
    seed        INTEGER NOT NULL,
    params      TEXT    NOT NULL,          -- JSON
    started_at  REAL    NOT NULL,
    solved_at   REAL,                      -- NULL until solved
    submits     INTEGER NOT NULL DEFAULT 0,
    xp_awarded  INTEGER NOT NULL DEFAULT 0,
    rep_awarded INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass
class Player:
    track: str
    xp: int
    rep: int


class SaveFile:
    def __init__(self, path: Path, track: str = "rhel"):
        path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the UI and the asyncio thread both use it;
        # every call here is short, and we commit immediately.
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            self.db.executescript(SCHEMA)
            self.db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self.db.execute("INSERT OR IGNORE INTO player (id, track, created_at) VALUES (1, ?, ?)",
                        (track, time.time()))
        self.db.commit()

    def player(self) -> Player:
        row = self.db.execute("SELECT track, xp, rep FROM player WHERE id = 1").fetchone()
        return Player(row["track"], row["xp"], row["rep"])

    def start_attempt(self, ticket_id: str, seed: int, values: dict) -> int:
        cur = self.db.execute(
            "INSERT INTO attempts (ticket_id, seed, params, started_at) VALUES (?, ?, ?, ?)",
            (ticket_id, seed, json.dumps(values), time.time()))
        self.db.commit()
        return cur.lastrowid

    def record_submit(self, attempt_id: int) -> None:
        self.db.execute("UPDATE attempts SET submits = submits + 1 WHERE id = ?", (attempt_id,))
        self.db.commit()

    def solve(self, attempt_id: int, xp: int, rep: int) -> Player:
        """Mark an attempt solved and add its rewards, in one transaction."""
        with self.db:   # commits on success, rolls back on error
            self.db.execute(
                "UPDATE attempts SET solved_at = ?, xp_awarded = ?, rep_awarded = ? WHERE id = ?",
                (time.time(), xp, rep, attempt_id))
            self.db.execute("UPDATE player SET xp = xp + ?, rep = rep + ? WHERE id = 1", (xp, rep))
        return self.player()

    def solved_ticket_ids(self) -> set[str]:
        rows = self.db.execute("SELECT DISTINCT ticket_id FROM attempts WHERE solved_at IS NOT NULL")
        return {r["ticket_id"] for r in rows}

    def close(self) -> None:
        self.db.close()
