"""Integration tests against the real VM (slow: needs QEMU and the base image).

    .venv\\Scripts\\python -m pytest tests\\test_vm.py -s

Set TEST_SOFTWARE=1 to test slow mode (software emulation) instead.
Set TEST_TICKETS=id1,id2 to check only those tickets.
In fast mode the warm spare is on, as it would be on a PC with 8 GB+ RAM.

Uses its own disk under data/ so it never touches your save game.
The first run boots Linux and saves the snapshot; later runs reuse it.
"""

import asyncio
import os
import time

import pytest

from client import config
from client.engine import grader, tickets
from client.vm.manager import VMManager

pytestmark = pytest.mark.skipif(not config.BASE_IMAGE.exists(),
                                reason="base image not built (run images/build_rhel.py)")

TRACK = "rhel"
SOFTWARE = os.environ.get("TEST_SOFTWARE") == "1"
# TEST_TICKETS=files-01-cleanup,files-02-links checks only those tickets (while writing them).
ONLY = {t for t in os.environ.get("TEST_TICKETS", "").split(",") if t}


@pytest.fixture
def test_disk(monkeypatch):
    # Separate disks: a snapshot taken in one mode can't be loaded in the other.
    folder = config.REPO_ROOT / "data" / ("test-vm-software" if SOFTWARE else "test-vm")
    monkeypatch.setattr(config, "OVERLAY_DISK", folder / "overlay.qcow2")
    monkeypatch.setattr(config, "SERIAL_LOG", folder / "serial.log")
    monkeypatch.setattr(config, "QEMU_LOG", folder / "qemu.log")


def test_reset_and_every_ticket(test_disk):
    asyncio.run(_scenario())


async def _scenario():
    vm = VMManager(force_software=SOFTWARE, warm_spare=not SOFTWARE)
    t0 = time.monotonic()
    await vm.start()
    print(f"\nstart: {time.monotonic() - t0:.1f}s, accel={vm.accel.name}, "
          f"snapshots={vm.snapshots_work}, spare={vm.spare_active}")
    try:
        # A reset must wipe changes.
        conn = await vm.root()
        await conn.run("touch /root/should-vanish", check=True)
        if vm.spare_active:
            await vm._spare_task          # let the spare finish booting, to time the swap itself
        t0 = time.monotonic()
        await vm.reset()
        reset_seconds = time.monotonic() - t0
        print(f"reset: {reset_seconds:.1f}s")
        if vm.spare_active:
            assert reset_seconds < 5, "swapping to a ready spare should take a second or two"
        conn = await vm.root()
        assert (await conn.run("test -e /root/should-vanish")).exit_status != 0

        # The clock was synced after the restore (within a few seconds of the host).
        guest_now = float((await conn.run("date +%s.%N", check=True)).stdout)
        assert abs(guest_now - time.time()) < 5

        for ticket in tickets.load_all(config.TICKETS_DIR, track=TRACK):
            if ONLY and ticket.id not in ONLY:
                continue
            await _check_ticket(vm, ticket)
    finally:
        await vm.stop()


def _two_different_seeds(ticket: tickets.Ticket) -> list[int]:
    """Seed 1, plus the seed (2..60) whose params differ from seed 1's the most.

    Fixed seeds 1 and 2 often rolled identical values (with only 2-3 choices
    per param), so a ticket's other branches (say, xz instead of gzip) went
    untested.
    """
    first = tickets.instantiate(ticket, seed=1).values
    def differences(seed):
        values = tickets.instantiate(ticket, seed=seed).values
        return sum(values[k] != first[k] for k in first)
    return [1, max(range(2, 61), key=differences)]


async def _check_ticket(vm: VMManager, ticket: tickets.Ticket):
    for seed in _two_different_seeds(ticket):     # two different param rolls
        await vm.reset()
        conn = await vm.root()
        inst = tickets.instantiate(ticket, seed=seed)
        print(f"{ticket.id} seed={seed} params={inst.values}")

        await grader.run_break(conn, inst, TRACK)
        await grader.prepare_player_shell(conn)      # as the game does (the man-page hook)
        before = await grader.run_grade(conn, inst, TRACK)
        assert not before.passed, f"{ticket.id}: grade passes right after break.sh"

        # Mentor steps with checks must not be already satisfied.
        checks = [s.check for s in ticket.mentor_steps if s.check]
        if checks:
            assert not await grader.mentor_check(conn, inst, checks[0])

        await grader.run_solution(conn, inst, TRACK)
        after = await grader.run_grade(conn, inst, TRACK)
        failing = [c.msg for c in after.checks if not c.passed]
        assert after.passed, f"{ticket.id}: solution.sh doesn't pass: {failing}\n{after.raw_output}"
        for check in checks:
            assert await grader.mentor_check(conn, inst, check), f"{ticket.id}: mentor check fails: {check}"
