# A new account without a password (useradd leaves it locked).
# Params: $NEWHIRE, $MAX_DAYS
set -euo pipefail
userdel -r "$NEWHIRE" &>/dev/null || true     # idempotent: a fresh account every time
useradd -m -c "New starter, Sales" "$NEWHIRE"
