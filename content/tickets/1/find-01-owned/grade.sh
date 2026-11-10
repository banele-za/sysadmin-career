# Every file sam owns under /srv and /home/sam must have an identical copy
# in $DEST, nothing of anyone else's may be there, and the originals stay.
# Params: $DEST
sams_files=$(find /srv /home/sam -user sam -type f)

all_copied() {
    local f
    for f in $sams_files; do
        cmp -s "$f" "$DEST/$(basename "$f")" || return 1
    done
}
only_sams() {          # every file in $DEST must be named like one of sam's
    local f
    for f in "$DEST"/* "$DEST"/.[!.]*; do
        [ -e "$f" ] || continue
        printf '%s\n' "$sams_files" | grep -qF "/$(basename "$f")" || return 1
    done
}

check dest "$DEST exists" \
    test -d "$DEST"

check all-copied "Every file owned by sam has a copy in $DEST ($(printf '%s\n' "$sams_files" | wc -l) files)" \
    all_copied

check only-sams "$DEST holds only sam's files" \
    only_sams

check originals "The originals are still in place" \
    test "$(find /srv /home/sam -user sam -type f | wc -l)" -ge 7

finish
