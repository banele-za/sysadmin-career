# The printer's log: mostly INFO, some WARN and ERROR, several users.
# Params: $HOME_DIR, $LOG, $SUSPECT
set -euo pipefail

rm -f "$HOME_DIR"/problems.txt "$HOME_DIR"/*-count.txt "$HOME_DIR"/denied.txt

users=(gary sam priya dave lena)
events=(
    "INFO job printed (3 pages)"
    "INFO job printed (1 page)"
    "INFO toner level 41%"
    "WARN paper tray 2 nearly empty"
    "INFO job printed (12 pages)"
    "ERROR paper jam in tray 1"
    "INFO job cancelled by user"
    "WARN job held: colour printing needs approval"
    "ERROR job failed: file is 900 pages of spreadsheet gridlines"
    "INFO job printed (2 pages)"
)
# 120 lines; the user and event follow a fixed pattern, so the log is the
# same every time and the grader can count on it.
: > "$LOG"
for i in $(seq 0 119); do
    user=${users[$(( (i * 7 + 3) % ${#users[@]} ))]}
    event=${events[$(( (i * 3 + i / 10) % ${#events[@]} ))]}
    printf '2026-11-%02d %02d:%02d %s user=%s\n' $(( i / 12 + 1 )) $(( 8 + i % 10 )) $(( (i * 17) % 60 )) \
        "$event" "$user" >> "$LOG"
done
chown admin:admin "$LOG"
