# Gary's files: a report open to everyone, a script nobody can run.
# Params: $DIR, $REPORT, $SCRIPT, $COLLEAGUE
set -euo pipefail

groupadd -f accounting
for u in gary "$COLLEAGUE"; do
    id "$u" &>/dev/null || useradd -m "$u"
    usermod -aG accounting "$u"
done
# Someone outside accounting, to check "everyone else nothing at all".
id intern &>/dev/null || useradd -m intern

rm -rf "$DIR"
mkdir -p "$DIR"
chown root:accounting "$DIR"
chmod 755 "$DIR"                    # anyone may look inside; the files decide the rest

echo "Q3 totals: 1,204,330.17 (do not share)" > "$DIR/$REPORT"
cat > "$DIR/$SCRIPT" <<'SCRIPT'
#!/bin/bash
echo "Monthly total: 98,112.40"
SCRIPT
chown gary:accounting "$DIR/$REPORT" "$DIR/$SCRIPT"
chmod 666 "$DIR/$REPORT"            # rw-rw-rw-: everyone can read and change it
chmod 664 "$DIR/$SCRIPT"            # rw-rw-r--: no x, and the team can edit it
