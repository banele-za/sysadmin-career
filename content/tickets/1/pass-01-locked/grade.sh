# Grade Gary's account from /etc/shadow.
# Params: $TEMP
# /etc/shadow fields: 2 hash ("!" in front = locked), 3 last change (0 = must
# change now), 8 account expiry (empty = never).
field() { getent shadow gary | cut -d: -f"$1"; }

# Does Gary's password hash match $TEMP? Python's crypt understands every
# hash type in /etc/shadow (RHEL 10 uses yescrypt, "$y$...").
password_is_temp() {
    TEMP="$TEMP" HASH="$(field 2)" python3 -W ignore -c '
import crypt, os, sys
h = os.environ["HASH"].lstrip("!")
sys.exit(0 if h and crypt.crypt(os.environ["TEMP"], h) == h else 1)'
}

check unlocked "Gary's account is unlocked" \
    test "$(field 2 | cut -c1)" != "!"

check not-expired "Gary's account no longer expires" \
    test -z "$(field 8)"

check temp-password "Gary's password is the temporary one, $TEMP" \
    password_is_temp

check must-change "Gary must choose a new password when he logs in" \
    test "$(field 3)" = 0

finish
