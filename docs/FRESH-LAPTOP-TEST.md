# Fresh Windows laptop test (Milestone 2)

The design doc asks for Milestone 2 to be "tested on a fresh Windows laptop".
Everything below has been tested on the development PC, partly with faked
problems (`SYSADMIN_GAME_FAKE`). This checklist covers what only a real
second machine can show. Write down what happened at each step; if anything
goes wrong, press **Copy diagnostic report** and keep the text.

## Before you start

- [ ] The laptop has never had this game, QEMU, or WSL/Hyper-V set up on purpose.
- [ ] Note the maker and model (for the BIOS guide), and how much RAM it has.
- [ ] The image release is uploaded and `IMAGE_RELEASE_URL` in `client/config.py`
      points at it (or set `SYSADMIN_GAME_IMAGE_URL`).

## Install (developer setup, until there's an installer)

- [ ] `winget install Python.Python.3.12` and `winget install SoftwareFreedomConservancy.QEMU`
- [ ] Copy or clone the repo, then `py -3.12 -m venv .venv` and
      `.venv\Scripts\pip install -r requirements.txt`
- [ ] Do **not** run `images\build_rhel.py`: the point is to test the download.

## First launch

- [ ] `.venv\Scripts\python -m client.app`
- [ ] The checkup screen appears within about 10 seconds.
- [ ] Every line is green, yellow or red with one understandable sentence.
- [ ] "Linux server image" offers **Download**. The progress bar moves; the
      download finishes; the checkup refreshes by itself.
- [ ] Time the download: ______ (about 600 MB).

## If fast mode is off (most likely on a fresh laptop)

- [ ] **Turn it on**: a Windows admin (UAC) prompt appears. Approve it.
- [ ] The game says a restart is needed, with **Restart now / Later**.
- [ ] After restarting, launch the game: is the "Windows virtualization
      setting" line green now? Is the badge "Fast mode"?
- [ ] Also try once: decline the UAC prompt. The game should say no changes
      were made, and still offer slow mode.

## If the BIOS switch is off

- [ ] **Show me how** opens the guide for the right brand (or "your PC").
- [ ] Is the setting name right for the CPU (Intel VT-x or AMD SVM)?
- [ ] **Restart into BIOS** restarts straight into the setup screen.
      If it doesn't, does the key in the guide work?
- [ ] Were the menu paths in the guide close to the real ones? Note the real
      path here, so the guide can be corrected: ______

## Slow mode

- [ ] **Play in slow mode** works. First boot takes several minutes (time it: ______).
- [ ] Next tickets reset in seconds (snapshots work in slow mode).
- [ ] The badge says "Slow mode · Try to fix again" and clicking it reopens the checkup.
- [ ] On a later launch, the game doesn't nag about slow mode again.
- [ ] After fixing fast mode, the next launch switches to fast mode by itself.

## Fast mode

- [ ] With 8 GB RAM or more: after finishing a ticket (and waiting about 30
      seconds), "Next ticket" is near-instant, thanks to the warm spare.
- [ ] Task Manager: closing the game leaves no `qemu-system-x86_64` running.
- [ ] Ending the game's Python process in Task Manager also ends QEMU.

## Report back

- [ ] Paste the diagnostic report, plus anything confusing in the wording.
