# Grade by trying things as the real users, so any correct chmod passes.
# Params: $DIR, $REPORT, $SCRIPT, $COLLEAGUE
report="$DIR/$REPORT"
script="$DIR/$SCRIPT"

check gary-owns "Gary still owns both files" \
    test "$(stat -c %U "$report")" = gary -a "$(stat -c %U "$script")" = gary

check gary-edits "Gary can read and write $REPORT" \
    as_user gary "test -r '$report' -a -w '$report'"

check team-reads "$COLLEAGUE (accounting) can read $REPORT" \
    as_user "$COLLEAGUE" "test -r '$report'"

check team-no-write "$COLLEAGUE can't change $REPORT" \
    as_user "$COLLEAGUE" "test ! -w '$report'"

check others-nothing "Someone outside accounting can't read $REPORT" \
    as_user intern "test ! -r '$report'"

check gary-runs "Gary can run $SCRIPT" \
    as_user gary "'$script'"

check script-locked "Only Gary can change $SCRIPT" \
    as_user "$COLLEAGUE" "test ! -w '$script'"

finish
