# Sysadmin Career Game: Design Doc

Oct 20, 2026 · @Banele

An incremental desktop game where the player climbs from help desk to sysadmin to sys engineer by fixing real problems on a real Linux VM, ending ready for RHCSA or SUSE SCA. Built in Python with Bash scenarios, one-click setup for non-technical players, and aimed at Steam once polished.

## Vision and pillars

The player learns real Linux administration by doing it on a real system, wrapped in a funny workplace story and an incremental progression loop.

1. **Real Linux, real skills.** Every ticket runs on an actual Linux VM. Grading checks the system's end state, so any valid solution passes.
2. **Exam-ready by the end.** All content maps to RHCSA or SUSE SCA objectives. Exam Mode simulates a timed exam, including a reboot before grading.
3. **Repetition without grind.** Skills come back again and again at rising difficulty, framed by recurring characters.
4. **Anyone can set it up.** Install, click Play, get a terminal. No manual installs, no Docker, no command-line setup.
5. **Small footprint.** One base image per distro track; every scenario is a script, never an image.

**Audience:** friends and colleagues first, then a public Steam release once polished.

## Core loop and economy

The player works a ticket queue; solving tickets earns progress, and automating solved ticket types turns them into passive income.

1. A ticket arrives from a character, with a short story-flavoured description.
2. The player fixes it in the terminal. The grader checks the VM's state.
3. The player earns **XP** (career progress toward promotion) and **reputation** (the spendable currency).
4. XP unlocks new command families, each introduced by a tutorial ticket.
5. Once a ticket type reaches Gold mastery, the player can write a script or systemd timer that handles it. That ticket class then resolves in the background and pays passive reputation.

**Reputation is spent on:** hints, cosmetic office upgrades, and unlocking optional side content. Exact amounts and rates are tuning work, decided during playtesting.

**Promotion:** reaching an XP threshold plus minimum mastery on that tier's core skills triggers a promotion story beat and the next tier.

The automation mechanic mirrors the real career: help desk does things by hand, sysadmins script them, engineers build systems that make the scripts unnecessary.

## Career tiers

Tier 1 is short; Tiers 2 and 3 are long and repetition-heavy, because they hold most of the exam material.

| Tier | Role | Skills taught | Ticket style | Length |
| --- | --- | --- | --- | --- |
| 1 | Help Desk | Navigation, file manipulation, basic permissions, `passwd`, reading logs, `grep` and pipes, finding files, `tar` | Small, explicit instructions | Short |
| 2 | Sysadmin | Users and groups, sudo, ACLs, package management, systemd services and targets, cron and timers, networking, firewall, SSH keys, journald | Vaguer ("the app is down"); diagnose before fixing | Long |
| 3 | Sys Engineer | Partitions, LVM, filesystems and persistent mounts, swap, SELinux or AppArmor, containers, boot problems and root password recovery, NFS and autofs, tuning | Multi-step chained incidents, some timed outages | Long |
| Final | Exam Mode | Everything | Timed practice exam, no hints, reboot before grading | One session, repeatable |

The exact skill list per tier must be finalised against the current official RHCSA and SCA objectives (see Open questions).

## Mastery and repetition

No skill appears once and disappears: every skill has a mastery ladder, and six systems keep pulling it back into the queue.

**Skill ladders.** Each skill climbs in complexity across tickets. Example for permissions:

| Level | Ticket flavour |
| --- | --- |
| 1 | Fix `chmod` on a single file |
| 2 | Ownership and group fixes with `chown` / `chgrp` |
| 3 | Shared team directory using setgid + umask |
| 4 | ACLs, including default ACLs for new files |
| 5 | Permissions look right but access is denied: the real problem is SELinux context or AppArmor |
| 6 | Mixed incident: a permissions problem buried inside a broken service |

Every skill family (services, storage, networking, scheduling, users, packages, security, containers, boot) gets a ladder of similar depth.

**Systems that drive repetition:**

- **Skill decay.** Each objective has a freshness meter. Stale skills are weighted into the queue more often: spaced repetition disguised as gameplay.
- **Randomised parameters.** Templates come back with different users, paths, ports and sizes, so answers can't be memorised.
- **Compound tickets.** Late tickets combine 3 to 4 skills, so early skills keep appearing inside later problems.
- **Mastery ranks** per objective: Bronze, Silver, Gold (Gold = solved without hints). Automation unlocks require Gold.
- **Quarterly audits.** Periodic events test a random spread of everything learned so far, as a mini Exam Mode.
- **Exam readiness screen.** Shows each objective's rank and freshness, so the player sees where they're weak.

## Distro tracks

The player picks Red Hat or SUSE at character creation; most content is shared, and each ticket carries distro-specific variants only where the systems differ.

| Area | Red Hat track | SUSE track |
| --- | --- | --- |
| Base image | Rocky Linux or AlmaLinux | openSUSE Leap |
| Certification target | RHCSA | SUSE SCA |
| Packages | dnf / rpm | zypper / rpm |
| Security module | SELinux | AppArmor |
| Filesystem focus | XFS, LVM | Btrfs + snapper, LVM |
| Admin tooling | nmcli, cockpit | YaST, nmcli / wicked |

Only the chosen track's image is downloaded. Switching tracks later is allowed and triggers a one-time download of the other image.

## Story and cast

The tone is light workplace comedy: a chaotic company whose recurring users keep breaking things, and each character is tied to a skill family so their tickets naturally drive repetition.

| Character | Running gag | Skills they drill |
| --- | --- | --- |
| Gary from Accounting | Chmods things to 777 "to make it work," then deletes them | Permissions, file recovery |
| Priya, the developer | Deploys containers that won't start; services enabled but never started | Containers, systemd, firewall |
| The Intern | Writes cron jobs that fill the disk at 3 AM | Scheduling, LVM extend, log cleanup |
| Dave, Security Lead | Turns on SELinux enforcing on Fridays without telling anyone | SELinux / AppArmor, troubleshooting |
| The VP | Wants "the server" fixed, gives no details | Vague-ticket diagnosis |
| The senior admin (mentor) | Runs tutorials, slowly retires as you level up | Tutorials |

**Story arc:** the player starts as the new help desk hire and ends as the senior engineer. The final beat: the mentor retires and the player becomes the mentor.

**Callbacks** ("Gary has learned a new command") make repeated skills feel like a running story instead of grind.

## Tutorials, hints and Exam Mode

Every new command family follows the same three steps: guided, unguided, then mixed into later work.

**Tutorial pattern**

1. **Guided ticket.** The mentor walks through the commands step by step in the chat panel.
2. **Unguided ticket.** A similar problem with different parameters and no walkthrough.
3. **Mixed in.** The skill starts appearing inside other tickets and compound incidents.

**Man pages first.** `man` and `--help` are taught in Tier 1 and rewarded (for example, bonus XP the first time a player solves a ticket after consulting a man page). Man pages are allowed in the real exams, so finding answers there is the most transferable skill.

**Hints cost reputation**, in three levels: a nudge, the command name, the full answer. Using any hint blocks Gold mastery on that solve.

**Exam Mode**

- Timed session with a mix of tickets across all objectives for the chosen track.
- No hints, no mentor, no tutorials.
- The VM is rebooted before grading, so anything that doesn't persist fails.
- Includes the boot-level tasks the real exam expects, such as root password recovery.
- Results feed the exam readiness screen.

## Technical architecture

A Python desktop client controls one hidden Linux VM; the player never sees the VM, only a terminal.

&#91;embedded content: architecture · client, one VM, content files\]

- **Client:** Python with pywebview for the window and xterm.js for the terminal, connected to the VM with `asyncssh`. Save data in SQLite.
- **VM:** bundled QEMU, user-mode networking with an SSH port forwarded to localhost, controlled through QMP for start, stop and snapshot restore. Acceleration: WHPX (Windows), HVF (Mac), KVM (Linux), software emulation as fallback.
- **Reset model:** the image is booted once and a running snapshot saved; each ticket restores it, runs `break.sh`, hands the terminal to the player, then runs `grade.sh`.
- **No containers.** They need Docker or Podman installed on Windows and Mac, which breaks the zero-setup goal. Container skills are taught with Podman inside the VM.

## Ticket format and grader contract

A ticket is a folder: one YAML file plus Bash scripts. Adding content never requires touching Python code.

```yaml
id: perm-03-setgid-shared
title: "The finance folder is a mess again"
tier: 2
skill: permissions
level: 3                      # position on the skill ladder
objectives: [perm.shared-dirs] # keys from objectives/<track>.yaml
character: gary
tracks: [rhel, suse]
params:
  group: { pick: [finance, payroll, audit] }
  dir: "/srv/{group}"
  users: { pick_n: 2, from: [alice, bob, carol, dan] }
narrative: |
  Gary says nobody can edit each other's files in {dir}.
  He tried chmod 777. It "sort of worked" until IT made him stop.
mentor_steps: []              # filled only for tutorial tickets
hints:
  - "New files should inherit the directory's group."
  - "Look at chmod g+s and umask."
  - "chgrp {group} {dir}; chmod 2770 {dir}"
requires_reboot: false
time_limit: null
rewards: { xp: 40, rep: 15 }
```

**Script contract**

- `break.sh` puts the VM into the broken state. Runs as root over SSH, receives params as environment variables, must be idempotent.
- `grade.sh` checks the end state, never the commands typed. Runs as root over SSH. Exit 0 = pass. Prints one JSON line per check (`{"check": "...", "pass": true, "msg": "..."}`) so the UI can show what's still wrong.
- Optional per-track overrides: `break.rhel.sh`, `grade.suse.sh` and so on, used when the track's tooling differs.
- Graders for persistence tickets run after a reboot.

**Objective keys** live in `objectives/rhcsa.yaml` and `objectives/sca.yaml`, built from the current official objective lists. Tickets reference keys, never free text.

## First-run experience

No player is ever locked out: every first launch ends in fast mode or slow mode, never an error screen. The only real blocker is hardware virtualization being switched off, mostly on Windows.

**1. Checkup.** Runs on first launch, whenever something breaks, and from Settings. Green / yellow / red per check, one plain-English sentence each.

| Check | Detection | Player sees |
| --- | --- | --- |
| Virtualization feature (Windows) | `Get-WindowsOptionalFeature` for Windows Hypervisor Platform | "A Windows setting needs to be turned on" → one-click fix |
| Virtualization in BIOS | WMI `VirtualizationFirmwareEnabled` (Windows), `/dev/kvm` (Linux), `kern.hv_support` (Mac) | "Your computer's speed boost is switched off" → picture guide |
| Linux permissions | `/dev/kvm` exists but isn't accessible | One-click fix |
| RAM | Total memory; VM needs about 2 GB | Yellow below threshold; VM sized down |
| Disk space | Free space vs. image size | Red, with the exact amount needed |
| Download | Image server reachable | Retry button |
| Smoke test | Launch QEMU with acceleration for a few seconds | Final word; overrides other checks |

A **Copy diagnostic report** button lets stuck players paste results to the developer.

**2. One-click fix.** Windows: "Turn it on" → admin prompt → enable feature → "Restart now / Later" → checkup re-runs on next launch. Linux: add user to `kvm` group via admin prompt, then log out and in. Mac: nothing to fix. A failed fix always leads to the picture guide or slow mode.

**3. Picture-guided BIOS instructions.** Detect the manufacturer via WMI and show that brand's guide (generic fallback). A "Restart into BIOS" button uses `shutdown /r /fw`. A QR code opens the guide on the player's phone. Illustrations are drawn in the game's style, not manufacturer screenshots, and name the setting to find (Intel VT-x, or AMD SVM / AMD-V). Every step reassures the player and offers "Skip, play in slow mode."

**4. Slow mode.** QEMU software emulation. Boot once during the story intro and save a running snapshot; every reset restores it instead of rebooting. Smaller VM, stretched timers, a warning before reboot tickets, and a "Slow mode" badge with "Try to fix again." Switches to fast mode automatically when a later checkup passes.

**Flow:** Launch → checkup → all green → download image → story intro while the VM boots → first ticket. Red → one-click fix → re-check → picture guide → re-check → slow mode.

## Size, distribution and Steam

The game stays small because scenarios are scripts, not images.

- **Rough budget:** a small client, one compressed base image (hundreds of MB to about 1 GB), and one VM disk that grows a bit. Hundreds of tickets fit in a few MB.
- **Images on demand.** The installer contains no Linux image; the chosen track's image downloads on first launch with a progress bar, and is verified with a checksum.
- **Images are built by us** from minimal cloud images (Rocky/Alma, openSUSE Leap) with an SSH key and the game's helper tools preinstalled. A build script in the repo produces them reproducibly.
- **CPU architecture.** Apple Silicon Macs need aarch64 images to get hardware acceleration; x86\_64 images would only run in slow mode there. Plan to build both architectures per track.
- **Licensing.** RHEL and SLES can't be redistributed; Rocky, Alma and openSUSE can. QEMU is GPL-licensed, so bundling it means shipping its source or a written offer; check this before release.
- **Trademarks.** Avoid implying official status. "Prepares you for RHCSA-style objectives" is safer than using Red Hat or SUSE marks in the title or store art. Get a proper check before the Steam page goes live.
- **Steam Deck** should work well, since it runs Linux with KVM support (to be verified).

## Suggested repo layout

A starting point; Claude Code can adjust it during planning.

```text
sysadmin-game/
├── docs/DESIGN.md            # this document
├── client/
│   ├── app.py                # pywebview entry point
│   ├── engine/               # ticket loader, params, scheduler, mastery, economy
│   ├── vm/                   # QEMU launch, QMP control, snapshots, accel detection
│   ├── ssh/                  # asyncssh session + terminal bridge
│   ├── checkup/              # first-run checks, fixes, diagnostic report
│   ├── save/                 # SQLite save data
│   └── ui/                   # HTML/CSS/JS, xterm.js, ticket + chat panels
├── content/
│   ├── objectives/           # rhcsa.yaml, sca.yaml
│   ├── characters/           # cast definitions
│   └── tickets/<tier>/<id>/  # ticket.yaml, break.sh, grade.sh
├── images/                   # scripts that build the base VM images
├── guides/                   # BIOS guide pages + illustrations
└── tests/                    # engine tests + ticket script tests against a VM
```

## Milestones

Build a thin working slice first, then scale content; each milestone ends with something playable.

1. **M1: Vertical slice (one platform, Red Hat track).** Image build script, QEMU launch with snapshot reset, SSH terminal in the pywebview window, ticket loader, one tutorial ticket + one unguided ticket with graders, XP and reputation counters, save file.
2. **M2: First-run experience.** Full checkup, one-click fixes, BIOS guide pages (placeholder art), slow mode, diagnostic report. Tested on a fresh Windows laptop.
3. **M3: Cross-platform.** Windows (WHPX), Mac (HVF, aarch64 image), Linux (KVM). Packaged builds for each.
4. **M4: Tier 1 content + story.** Full help desk tier, mentor tutorials, Gary and the Intern, hints.
5. **M5: Progression systems.** Mastery ranks, skill decay scheduling, compound tickets, automation unlocks, exam readiness screen.
6. **M6: SUSE track.** Second image, per-track ticket variants, AppArmor and Btrfs content.
7. **M7: Tiers 2 and 3 content.** The long, repetition-heavy bulk of the game.
8. **M8: Exam Mode + audits.**
9. **M9: Friends-and-colleagues beta**, then polish, art, and Steam.

## Open questions

- [ ] Pull the current official RHCSA and SUSE SCA objective lists and build `objectives/*.yaml` from them.
- [ ] Game title and art style.
- [ ] Packaging tool for the Python client (PyInstaller, Briefcase or similar).
- [ ] Where VM images are hosted for download, and bandwidth cost at Steam scale.
- [ ] QEMU licensing obligations and trademark review before release.
- [ ] Whether slow-mode snapshot restore is fast enough on low-end hardware; prototype early.
- [ ] Economy tuning: XP curve, reputation costs, automation payout rates.
- [ ] Browser demo (parked).
