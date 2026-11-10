# Grade the two links by what they are, not how they were made.
# Params: $MONTH, $REPORT, $SHORTCUT, $SAFETY

check report-kept "The report itself is still at $REPORT" \
    test -f "$REPORT" -a ! -L "$REPORT"

check shortcut-symlink "$SHORTCUT is a symbolic link" \
    test -L "$SHORTCUT"

check shortcut-target "$SHORTCUT leads to the report" \
    test "$(readlink -f "$SHORTCUT")" = "$(readlink -f "$REPORT")"

check gary-follows "Gary can open the report through his shortcut" \
    as_user gary "cat '$SHORTCUT' >/dev/null"

check safety-hard "$SAFETY is a hard link: same data as the report, not a copy" \
    test -f "$SAFETY" -a ! -L "$SAFETY" -a "$(stat -c %i "$SAFETY")" = "$(stat -c %i "$REPORT")"

finish
