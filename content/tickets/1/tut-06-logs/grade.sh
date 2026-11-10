# Grade the log-reading tutorial by its two answers.
# Params: $HOME_DIR, $BADUSER, $IP, $DISK

check intruder "~/intruder.txt names the account they tried: $BADUSER" \
    grep -qw "$BADUSER" "$HOME_DIR/intruder.txt"

check missing-disk "~/missing-disk.txt names the missing backup disk: $DISK" \
    grep -qF "$DISK" "$HOME_DIR/missing-disk.txt"

finish
