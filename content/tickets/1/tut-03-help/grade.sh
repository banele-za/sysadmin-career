# Grade the help tutorial by its two answers, and by a man page having been read.
# Params: $HOME_DIR, $YEAR, $QUARTER

check read-manual "You opened a man page" \
    test -e /tmp/.sysadmin-game-read-docs

check nested-folders "~/projects/$YEAR/$QUARTER exists" \
    test -d "$HOME_DIR/projects/$YEAR/$QUARTER"

check folders-yours "The new folders belong to you" \
    test "$(stat -c %U "$HOME_DIR/projects" 2>/dev/null)" = admin

check home-field "~/home-field.txt says the home directory is field 6" \
    grep -qxE '[[:space:]]*6[[:space:]]*' "$HOME_DIR/home-field.txt"

finish
