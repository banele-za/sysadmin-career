# Grade from /etc/shadow: password set, expired for first login, aging set.
# Params: $NEWHIRE, $MAX_DAYS
# /etc/shadow fields: 1 name, 2 hash, 3 last change (0 = must change now), 5 max days.
field() { getent shadow "$NEWHIRE" | cut -d: -f"$1"; }

check has-password "$NEWHIRE has a password (status P)" \
    sh -c "passwd -S '$NEWHIRE' | awk '{exit !(\$2 == \"P\" || \$2 == \"PS\")}'"

check must-change "$NEWHIRE must choose a new password at first login" \
    test "$(field 3)" = 0

check max-days "Passwords expire after $MAX_DAYS days" \
    test "$(field 5)" = "$MAX_DAYS"

finish
