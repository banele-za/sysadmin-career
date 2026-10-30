"""When does the checkup screen appear, and what do its buttons do?

Uses made-up facts and a stand-in VM, so it runs in a second without QEMU.
"""

import asyncio

import pytest

from client import config, game as game_mod, host
from client.checkup.facts import GB, Facts


def facts(**changes) -> Facts:
    f = Facts(platform="win32", manufacturer="Acer", cpu_vendor="amd", ram_bytes=16 * GB,
              disk_free_bytes=100 * GB, firmware_virt=True, hypervisor_present=True,
              windows_features={"HypervisorPlatform": "enabled"},
              image_present=True, smoke_ok=True, smoke_accel="whpx")
    for key, value in changes.items():
        setattr(f, key, value)
    return f


class World:
    """What the fake PC looks like right now; tests change it between launches."""

    def __init__(self):
        self.facts = facts()
        self.vm_failures = 0          # how many VM starts should still fail
        self.vm_started_with = []


@pytest.fixture
def world(monkeypatch, tmp_path):
    w = World()
    monkeypatch.setattr(config, "SAVE_DB", tmp_path / "save.db")
    monkeypatch.setattr(game_mod.facts_mod, "gather", lambda: w.facts)

    async def fake_start_vm(self):
        w.vm_started_with.append((self.checkup.mode, self.checkup.vm_memory_mb, self.checkup.warm_spare))
        if w.vm_failures:
            w.vm_failures -= 1
            raise RuntimeError("QEMU failed to start: pretend")

    async def no_ticket(self):
        self.emit({"type": "ticket_started"})

    monkeypatch.setattr(game_mod.Game, "_start_vm", fake_start_vm)
    monkeypatch.setattr(game_mod.Game, "next_ticket", no_ticket)
    return w


class UI(list):
    def __call__(self, event):
        self.append(event)

    def types(self):
        return [e["type"] for e in self]


async def shown(ui: UI, times: int, timeout: float = 5) -> None:
    """Wait until the checkup screen has been shown `times` times."""
    async with asyncio.timeout(timeout):
        while ui.types().count("checkup") < times:
            await asyncio.sleep(0.01)


async def launch(ui: UI, *clicks: str) -> game_mod.Game:
    """Start a game session, pressing one button on each checkup screen shown.

    Waits for each screen to actually appear before clicking: a fixed pause
    was too short on GitHub's slower machines, and the click got lost.
    """
    g = game_mod.Game(ui)
    starting = asyncio.create_task(g.start())
    for n, action in enumerate(clicks, start=1):
        await shown(ui, n)
        await g.checkup_action(action)
    await asyncio.wait_for(starting, 5)
    g.save.close()
    return g


def run(coro):
    return asyncio.run(coro)


def test_first_run_shows_checkup_then_not_again(world):
    ui = UI()
    run(launch(ui, "continue"))
    assert ui.types().count("checkup") == 1 and "ticket_started" in ui.types()

    ui2 = UI()
    run(launch(ui2))                                   # second launch, all green: straight in
    assert "checkup" not in ui2.types()


def test_slow_mode_choice_is_remembered_until_fast_works(world):
    world.facts = facts(smoke_ok=False, windows_features={"HypervisorPlatform": "disabled"})
    run(launch(UI(), "slow_mode"))
    ui = UI()
    run(launch(ui))                                    # accepted slow mode: no nagging
    assert "checkup" not in ui.types()
    assert world.vm_started_with[-1][0] == "slow"

    world.facts = facts()                              # player fixed it: fast mode
    run(launch(UI()))
    assert world.vm_started_with[-1] == ("fast", 2048, True)

    world.facts = facts(smoke_ok=False, windows_features={"HypervisorPlatform": "disabled"})
    ui = UI()
    run(launch(ui, "slow_mode"))                       # broke again: tell them again
    assert "checkup" in ui.types()


def test_blocking_problem_holds_the_game_until_fixed(world):
    world.facts = facts(image_present=False, download_configured=True, download_reachable=False)

    async def scenario():
        ui = UI()
        g = game_mod.Game(ui)
        starting = asyncio.create_task(g.start())
        await shown(ui, 1)
        await g.checkup_action("continue")             # ignored: no image yet
        await asyncio.sleep(0.2)
        assert not starting.done()
        world.facts = facts()                          # e.g. the internet came back + downloaded
        await g.checkup_action("retry")
        await g.checkup_action("continue")
        await asyncio.wait_for(starting, 5)
        assert ui.types().count("checkup") == 2
        g.save.close()

    run(scenario())


def test_vm_failure_reopens_checkup_with_error(world):
    world.vm_failures = 1
    ui = UI()
    run(launch(ui, "continue", "continue"))            # first run, then "Try again"
    screens = [e for e in ui if e["type"] == "checkup"]
    assert screens[0]["error"] == ""
    assert "QEMU failed to start" in screens[1]["error"]
    assert "ticket_started" in ui.types()


def test_low_ram_shrinks_the_vm(world):
    world.facts = facts(ram_bytes=4 * GB)
    run(launch(UI(), "continue"))
    assert world.vm_started_with[-1] == ("fast", config.VM_MEMORY_SMALL_MB, False)


def test_bios_guide_and_fake_fix(world, monkeypatch):
    monkeypatch.setenv("SYSADMIN_GAME_FAKE", "bios-off")   # fixes only describe themselves
    world.facts = facts(smoke_ok=False, firmware_virt=False, hypervisor_present=False)

    async def scenario():
        ui = UI()
        g = game_mod.Game(ui)
        starting = asyncio.create_task(g.start())
        await shown(ui, 1)
        await g.checkup_action("bios_guide")
        guide = next(e for e in ui if e["type"] == "guide")
        assert guide["brand"] == "Acer" and "SVM" in guide["setting"]
        await g.checkup_action("restart_bios")
        notice = [e for e in ui if e["type"] == "checkup_notice"][-1]
        expected = " ".join(host.restart_command(into_firmware=True))   # shutdown /r ... /fw on Windows
        assert "Test mode" in notice["text"] and expected in notice["text"]
        await g.checkup_action("slow_mode")
        await asyncio.wait_for(starting, 5)
        g.save.close()

    run(scenario())
