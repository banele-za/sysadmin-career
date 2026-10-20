# Gary's "fix": a world-writable folder whose files keep their creators' groups.
# Params: $GROUP, $DIR, $USERS (space-separated)
set -euo pipefail

groupadd -f "$GROUP"
for u in $USERS; do
    id "$u" &>/dev/null || useradd -m "$u"
    usermod -aG "$GROUP" "$u"
done
# Gary exists but is not in the group.
id gary &>/dev/null || useradd -m gary

rm -rf "$DIR"
mkdir -p "$DIR"
chown root:root "$DIR"
chmod 0777 "$DIR"

# Each user already saved a report. Created through a login shell, the file
# gets the user's own private group (alice:alice) and, with RHEL 10's umask
# 022, mode rw-r--r--, so colleagues can't edit it.
for u in $USERS; do
    as_user "$u" "echo 'Q3 figures, draft by $u' > '$DIR/$u-report.txt'"
done
