# common.sh: helpers available to every break.sh, grade.sh and solution.sh.
# The game pastes this file in front of the ticket's script before running it,
# so these functions are simply there; no `source` needed.

# Ticket params arrive as environment variables (group -> $GROUP).

# --- grading ---------------------------------------------------------------

_FAILED=0

# Escape a string for use inside a JSON "..." value.
_json_escape() {
    local s=$1
    s=${s//\\/\\\\}      # backslash -> \\
    s=${s//\"/\\\"}      # quote     -> \"
    s=${s//$'\n'/ }      # newline   -> space
    s=${s//$'\t'/ }      # tab       -> space
    printf '%s' "$s"
}

# check NAME MESSAGE COMMAND [ARGS...]
#   Runs COMMAND. Prints one JSON result line; remembers failures for finish.
#   Example:  check group-owner "$DIR belongs to $GROUP" \
#                 test "$(stat -c %G "$DIR")" = "$GROUP"
check() {
    local name=$1 msg=$2
    shift 2
    local pass=false
    if "$@" >/dev/null 2>&1; then
        pass=true
    else
        _FAILED=1
    fi
    printf '{"check": "%s", "pass": %s, "msg": "%s"}\n' \
        "$(_json_escape "$name")" "$pass" "$(_json_escape "$msg")"
}

# finish: call at the end of grade.sh. Exit 0 only if every check passed.
finish() {
    exit "$_FAILED"
}

# --- running things as the ticket's users ------------------------------------

# as_user USER COMMAND...
#   Run a command as USER through a login shell, so their real umask and
#   group memberships apply, exactly as if they had logged in.
as_user() {
    local user=$1
    shift
    runuser -l "$user" -c "$*"
}
