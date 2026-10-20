"""Run break.sh / grade.sh on the VM and interpret the grader's output.

Grader contract (docs/DESIGN.md): grade.sh prints one JSON line per check,
    {"check": "group-owner", "pass": true, "msg": "/srv/finance belongs to finance"}
and exits 0 when the ticket is solved. Any other output is ignored, so a
stray `echo` in a grader can't break the UI.

Both scripts get content/lib/common.sh prepended, which provides the
`check` helper that prints those JSON lines.
"""

import json
from dataclasses import dataclass

from client import config
from client.engine.tickets import TicketInstance
from client.ssh import session

LIB = config.CONTENT_DIR / "lib" / "common.sh"


@dataclass
class Check:
    name: str
    passed: bool
    msg: str


@dataclass
class GradeResult:
    passed: bool
    checks: list[Check]
    raw_output: str   # kept for debugging graders


def _with_lib(script: str) -> str:
    return LIB.read_text(encoding="utf-8").replace("\r\n", "\n") + "\n" + script


def parse_output(stdout: str, exit_status: int) -> GradeResult:
    checks = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "check" in item and "pass" in item:
            checks.append(Check(str(item["check"]), bool(item["pass"]), str(item.get("msg", ""))))
    # Pass needs both: exit 0 and no failing check (guards against a grader
    # that forgets to set its exit code).
    passed = exit_status == 0 and all(c.passed for c in checks)
    return GradeResult(passed, checks, stdout)


async def run_break(conn, instance: TicketInstance, track: str) -> None:
    script = instance.ticket.script("break", track)
    result = await session.run_script(conn, _with_lib(script), instance.env)
    if result.exit_status != 0:
        raise RuntimeError(f"break.sh failed for {instance.ticket.id}:\n{result.stderr}")


async def run_grade(conn, instance: TicketInstance, track: str) -> GradeResult:
    script = instance.ticket.script("grade", track)
    result = await session.run_script(conn, _with_lib(script), instance.env)
    return parse_output(result.stdout, result.exit_status)


async def run_solution(conn, instance: TicketInstance, track: str) -> None:
    """Apply the reference fix (tests only)."""
    script = instance.ticket.script("solution", track)
    if script is None:
        raise RuntimeError(f"{instance.ticket.id} has no solution.sh")
    result = await session.run_script(conn, _with_lib(script), instance.env)
    if result.exit_status != 0:
        raise RuntimeError(f"solution.sh failed for {instance.ticket.id}:\n{result.stderr}")


async def mentor_check(conn, instance: TicketInstance, check_script: str) -> bool:
    """True if a mentor step's check passes (exit 0)."""
    result = await session.run_script(conn, _with_lib(check_script), instance.env, timeout=20)
    return result.exit_status == 0
