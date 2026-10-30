# Grade the permissions tutorial by looking at the final files.
# Params: $SCRIPT, $SECRET, $GROUP, $LESSON, $HANDOVER
script="$LESSON/$SCRIPT"
secret="$LESSON/$SECRET"
report="$HANDOVER/report.txt"

# Behaviour, not exact modes: admin must be able to run it.
check script-runs "admin can run $SCRIPT" \
    as_user admin "'$script'"

check secret-private "$SECRET is readable only by its owner (mode 600)" \
    test "$(stat -c %a "$secret")" = 600

check report-owner "report.txt is owned by admin" \
    test "$(stat -c %U "$report")" = admin

check report-group "report.txt belongs to the $GROUP group" \
    test "$(stat -c %G "$report")" = "$GROUP"

# The tempting shortcut, chmod 777, makes files writable by everyone.
check not-world-writable "Nothing was made writable by everyone (no chmod 777 shortcuts)" \
    test -z "$(find "$LESSON" "$HANDOVER" -perm -o+w)"

finish
