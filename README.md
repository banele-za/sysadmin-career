# Sysadmin Career (working title)

A desktop game that teaches Linux administration (RHCSA / SUSE SCA style
objectives) by having you fix real problems on a hidden Linux VM.
Design: [docs/DESIGN.md](docs/DESIGN.md). Done so far: Milestone 1 (vertical
slice: Red Hat track, Windows, a five-ticket ladder) and Milestone 2 (first-run
checkup, one-click fixes, BIOS guides, slow mode, image download).

## Setup (Windows, development)

```powershell
winget install Python.Python.3.12
winget install SoftwareFreedomConservancy.QEMU
py -3.12 -m venv .venv          # or: & "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python images\build_rhel.py      # one-time, ~5 min + download
.venv\Scripts\python -m client.app              # play
```

Without `build_rhel.py`, the game downloads the image instead (players do
this), from `IMAGE_RELEASE_URL` in `client/config.py`.

## First launch: the checkup

Every launch runs a quick checkup (Windows settings, BIOS virtualization, RAM,
disk, image, and a QEMU speed test). The screen only appears on the first
launch, when something blocks the game, or when fast mode stops working; the
**Checkup** button in the top bar opens it any time.

- **Fast mode** (hardware virtualization, WHPX). Resets reboot the VM, since
  WHPX can't snapshot, but with 8 GB+ RAM a **warm spare** VM boots in the
  background, so "Next ticket" is near-instant.
- **Slow mode** (software emulation): nobody is locked out. The first boot is
  slow; after that, resets restore a snapshot in seconds. Force it with `--software`.

Test the unhappy paths without breaking your PC:

```powershell
$env:SYSADMIN_GAME_FAKE = "bios-off,low-ram"   # also: feature-off, tiny-ram, low-disk, no-image, offline
$env:SYSADMIN_GAME_DATA = "$env:TEMP\sg-test"  # a throwaway save, so the first-run screen shows
.venv\Scripts\python -m client.app
```

While faking, the fixes only describe what they would do. To test on a
second PC, follow [docs/FRESH-LAPTOP-TEST.md](docs/FRESH-LAPTOP-TEST.md).

Your save, the VM's working disks and `game.log` live in
`%LOCALAPPDATA%\SysadminGame` (override with `SYSADMIN_GAME_DATA`). Delete
`vm\` there for a factory-fresh VM.

## Publishing the image

```powershell
.venv\Scripts\python images\release.py     # writes images\release\ (about 600 MB)
```

Upload the four files in `images\release\` to one GitHub Release, and set
`IMAGE_RELEASE_URL` to `https://github.com/<owner>/<repo>/releases/download/<tag>/`.
The game checks every file against `manifest.json`'s SHA-256 before using it.

## Tests

```powershell
.venv\Scripts\python -m pytest tests --ignore=tests\test_vm.py --ignore=tests\test_game.py   # fast, no VM
.venv\Scripts\python -m pytest tests\test_vm.py -s                        # every ticket on the real VM
.venv\Scripts\python -m pytest tests\test_game.py -s                      # headless playthrough
```

`test_vm.py` runs every ticket twice with different params: grading must fail
after `break.sh` and pass after the ticket's `solution.sh`. Set
`TEST_SOFTWARE=1` to run it in slow mode.

## Layout

```text
client/
  app.py          window + threads (pywebview)
  game.py         the ticket flow: reset -> break -> play -> grade -> reward
  config.py       every path and setting
  checkup/        first-run checks, fixes, BIOS guides, image download, diagnostic report
  vm/             accel detection, QEMU command line, QMP client, VM manager (+ warm spare)
  ssh/            asyncssh helpers and the terminal bridge
  engine/         ticket loader, params, grader, economy, progression (the ladder)
  save/           SQLite save file
  ui/             HTML/CSS/JS, vendored xterm.js
content/
  lib/common.sh   helpers pasted in front of every ticket script
  objectives/     objective keys tickets can reference
  characters/     display names for ticket characters
  tickets/<tier>/<id>/   ticket.yaml, break.sh, grade.sh, solution.sh
guides/           BIOS guide data per PC maker (placeholder content)
images/           base image build + release scripts, cloud-init config
docs/             design doc, fresh-laptop test checklist
tests/
```

## Writing a ticket

Copy a folder under `content/tickets/`, rename it to the new id, and edit it.
No Python changes needed. The ticket.yaml format is in docs/DESIGN.md, plus:

- **The ladder.** Players meet tickets in order of tier, then `level`, with
  guided tickets before unguided ones (`engine/progression.py`). A ticket
  unlocks once every lower tier is done and every lower-level ticket of the
  same `skill`. Each skill must start with a guided level-1 ticket and climb
  one level at a time; `test_progression.py` enforces this, so a new ticket
  can't throw beginners into the deep end. Teach a new command family with a
  guided ticket first, then practise it unguided.

- **Params** become upper-case environment variables (`group` -> `$GROUP`).
  Lists are space-separated (`for u in $USERS`). Names like `home` or `path`
  are rejected because they'd overwrite `$HOME` / `$PATH`.
- **`mentor_steps`** (guided tickets): a list of `{say: ..., check: ...}`.
  `say` may use `{param}`. `check` is Bash run as root every 2 s; exit 0
  moves to the next step. Omit `check` to show a "Got it" button instead.
  A check must **stay true after later steps** (e.g. accept the renamed file
  too), otherwise a player who does two steps between polls gets stuck.
  `test_vm.py` enforces this.
- **`mentor_intro`** (unguided tickets, optional): one mentor message shown
  at the start. Use it to explain a new *idea* without giving the commands.
- **`grade.sh`** uses `check NAME MESSAGE COMMAND...` and ends with `finish`.
  Prefer testing behaviour (`as_user alice "..."`) over exact modes, so
  every valid solution passes.
- **`solution.sh`** is a reference fix used only by tests.
