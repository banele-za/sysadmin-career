# Grade the grep tutorial by the files it asked for. The expected content is
# computed from the log itself, so any way of producing it passes.
# Params: $HOME_DIR, $LOG, $SUSPECT

check problems "~/problems.txt has the ERROR lines, then the WARN lines" \
    test "$(cat "$HOME_DIR/problems.txt" 2>/dev/null)" = "$(grep ERROR "$LOG"; grep WARN "$LOG")"

check count "~/$SUSPECT-count.txt has the number of lines mentioning $SUSPECT" \
    test "$(tr -d '[:space:]' < "$HOME_DIR/$SUSPECT-count.txt" 2>/dev/null)" = "$(grep -c "$SUSPECT" "$LOG")"

check stderr "~/denied.txt caught the 'Permission denied' error" \
    grep -q "Permission denied" "$HOME_DIR/denied.txt"

finish
