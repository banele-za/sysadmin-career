# Grade ownership by looking at every file, then by trying it as the users.
# Params: $LEAVER, $NEWOWNER, $TEAMMATE, $TEAM, $PROJECT, $DIR
draft="$DIR/drafts/draft-1.txt"

check owner-all "$NEWOWNER owns $DIR and everything in it" \
    test -z "$(find "$DIR" ! -user "$NEWOWNER")"

check group-all "Everything in $DIR belongs to the $TEAM group" \
    test -z "$(find "$DIR" ! -group "$TEAM")"

check newowner-edits "$NEWOWNER can edit files, even in the drafts subfolder" \
    as_user "$NEWOWNER" "test -w '$draft' -a -w '$DIR/plan.txt'"

check team-reads "$TEAMMATE ($TEAM) can read the files" \
    as_user "$TEAMMATE" "cat '$draft' '$DIR/plan.txt'"

check team-no-write "$TEAMMATE can read but not change them (permissions left alone)" \
    as_user "$TEAMMATE" "test ! -w '$DIR/plan.txt'"

check outsiders-out "Gary (not in $TEAM) still can't get in" \
    bash -c "! runuser -l gary -c 'ls $DIR'"

finish
