# Practice files for the permissions tutorial.
# Params: $SCRIPT, $SECRET, $GROUP, $LESSON, $HANDOVER
set -euo pipefail

rm -rf "$LESSON" "$HANDOVER"          # idempotent: start from scratch
mkdir -p "$LESSON" "$HANDOVER"

# A script with no execute permission for anyone: rw-r--r-- (644).
cat > "$LESSON/$SCRIPT" <<'SCRIPT'
#!/bin/bash
echo "It runs! You just gave this file permission to execute."
SCRIPT
chmod 644 "$LESSON/$SCRIPT"

# A "private" file everyone can read (644).
echo "Note to self: learn chmod." > "$LESSON/$SECRET"
chmod 644 "$LESSON/$SECRET"
chown -R admin:admin "$LESSON"

# A root-owned report the player must take over with sudo.
groupadd -f "$GROUP"
echo "Shift handover: printer on floor 2 is out of toner again." > "$HANDOVER/report.txt"
chown root:root "$HANDOVER/report.txt"
chmod 644 "$HANDOVER/report.txt"
