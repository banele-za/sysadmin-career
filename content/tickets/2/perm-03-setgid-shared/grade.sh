# Grade the shared folder by trying things as the real users, not by
# demanding one exact mode: 2770, 3770 (plus sticky bit) or an equivalent
# fix all pass, as long as they actually work.
# Params: $GROUP, $DIR, $USERS
read -r user1 user2 <<< "$USERS"

mode=$(stat -c %a "$DIR")          # e.g. 2770
perm=$(stat -c %A "$DIR")          # e.g. drwxrws---

check dir-group "$DIR belongs to the $GROUP group" \
    test "$(stat -c %G "$DIR")" = "$GROUP"

check setgid "$DIR has the setgid bit, so new files inherit the $GROUP group" \
    test -g "$DIR"

check group-rwx "Members of $GROUP can read, write and enter $DIR" \
    test "${perm:4:3}" = rws -o "${perm:4:3}" = rwx

check no-others "Users outside $GROUP have no access (now $perm, mode $mode)" \
    test "${perm:7:3}" = "---"

# Behaviour: a brand new file from user1 must be editable by user2.
probe="$DIR/.grader-probe-$$"
as_user "$user1" "echo probe > '$probe'" 2>/dev/null
check new-file-shared "A new file made by $user1 can be edited by $user2" \
    as_user "$user2" "echo edit >> '$probe'"
rm -f "$probe"

# The reports that were already there must be shared too.
check old-file-shared "$user2 can edit $user1's existing report" \
    as_user "$user2" "test -w '$DIR/$user1-report.txt'"
check old-file-shared-2 "$user1 can edit $user2's existing report" \
    as_user "$user1" "test -w '$DIR/$user2-report.txt'"

check gary-out "Gary (not in $GROUP) can't list $DIR" \
    bash -c "! runuser -l gary -c 'ls $DIR'"

finish
