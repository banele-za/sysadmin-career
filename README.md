# Sysadmin Career (working title)

A desktop game that teaches Linux administration (RHCSA / SUSE SCA style
objectives) by having you fix real problems on a hidden Linux VM.
Design: [docs/DESIGN.md](docs/DESIGN.md). This is Milestone 1, the vertical
slice: Red Hat track, Windows, a five-ticket ladder (files, then permissions).

## Setup (Windows, development)

```powershell
winget install Python.Python.3.12
winget install SoftwareFreedomConservancy.QEMU
py -3.12 -m venv .venv          # or: & "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python images\build_rhel.py      # one-time, ~5 min + download
.venv\Scripts\python -m client.app              # play
```

Fast mode needs the Windows feature "Windows Hypervisor Platform". Without it
the game still runs in slow (software) mode; force that with `--software`.

The first launch boots Linux and saves a snapshot (about a minute).
After that, every ticket starts from that snapshot in a few seconds.

Your save and the VM's working disk live in `%LOCALAPPDATA%\SysadminGame`
(override with `SYSADMIN_GAME_DATA`). Delete `vm\overlay.qcow2` there for a
factory-fresh VM.

## Tests

```powershell
.venv\Scripts\python -m pytest tests\test_engine.py tests\test_save.py tests\test_progression.py   # fast, no VM
.venv\Scripts\python -m pytest tests\test_vm.py -s                     # boots the real VM
```

`test_vm.py` runs every ticket twice with different params: grading must fail
after `break.sh` and pass after the ticket's `solution.sh`.

## Layout

```text
client/
  app.py          window + threads (pywebview)
  game.py         the ticket flow: reset -> break -> play -> grade -> reward
  config.py       every path and setting
  vm/             accel detection, QEMU command line, QMP client, VM manager
  ssh/            asyncssh helpers and the terminal bridge
  engine/         ticket loader, params, grader, economy, progression (the ladder)
  save/           SQLite save file
  ui/             HTML/CSS/JS, vendored xterm.js
content/
  lib/common.sh   helpers pasted in front of every ticket script
  objectives/     objective keys tickets can reference
  characters/     display names for ticket characters
  tickets/<tier>/<id>/   ticket.yaml, break.sh, grade.sh, solution.sh
images/           base image build script and cloud-init config
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
