# Grade the tidy-up by the final layout of the folder.
# Params: $HOME_DIR, $DUMP, $KEEP
dump="$HOME_DIR/$DUMP"

count() { find "$1" -maxdepth 1 -type f -name "$2" 2>/dev/null | wc -l; }

check photos "photos/ holds all 5 .jpg files" \
    test "$(count "$dump/photos" '*.jpg')" -eq 5

check docs "docs/ holds all 3 .pdf files" \
    test "$(count "$dump/docs" '*.pdf')" -eq 3

check sorted "No .jpg or .pdf files are left loose in ~/$DUMP" \
    test "$(count "$dump" '*.jpg')" -eq 0 -a "$(count "$dump" '*.pdf')" -eq 0

check junk-gone "The .tmp junk is gone (from everywhere in ~/$DUMP)" \
    test "$(find "$dump" -name '*.tmp' 2>/dev/null | wc -l)" -eq 0

check backup "~/backup/$KEEP is a copy of the original" \
    cmp -s "$dump/$KEEP" "$HOME_DIR/backup/$KEEP"

check original-kept "The original $KEEP is still in ~/$DUMP" \
    test -f "$dump/$KEEP"

check notes-kept "Nothing else was deleted (notes.txt is still there)" \
    test -f "$dump/notes.txt"

finish
