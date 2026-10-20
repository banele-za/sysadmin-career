# Grade the onboarding tutorial by looking at the final files only.
# Params: $CODEWORD, $HOME_DIR
notes="$HOME_DIR/notes"

check notes-dir "You have a notes folder in your home" \
    test -d "$notes"

check renamed "welcome.txt was copied to notes and renamed to $CODEWORD.txt" \
    cmp -s "$HOME_DIR/onboarding/welcome.txt" "$notes/$CODEWORD.txt"

check no-leftover "There's no welcome.txt left in notes (it was renamed, not copied twice)" \
    test ! -e "$notes/welcome.txt"

check original-kept "The original onboarding/welcome.txt is still there" \
    test -f "$HOME_DIR/onboarding/welcome.txt"

check junk-gone "DELETE-ME.tmp has been removed" \
    test ! -e "$HOME_DIR/onboarding/DELETE-ME.tmp"

check done-file "notes/done exists" \
    test -f "$notes/done"

# Work done as the admin user means admin owns the results.
check owned-by-admin "Your notes belong to you (user admin)" \
    test "$(stat -c %U "$notes" 2>/dev/null)" = admin

finish
