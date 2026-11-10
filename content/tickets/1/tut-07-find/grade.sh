# Grade the three answers. Expected lists come from find itself, run as
# admin (so they show exactly what the player can see).
# Params: $HOME_DIR, $SHARE, $LOST
as_admin_find() { runuser -u admin -- find "$SHARE" "$@" 2>/dev/null; }

check found "~/found.txt has the full path of $LOST" \
    grep -qx "$(find "$SHARE" -name "$LOST" | head -n 1)" "$HOME_DIR/found.txt"

check big-files "~/big-files.txt lists every file over 5 MB" \
    test "$(sort "$HOME_DIR/big-files.txt" 2>/dev/null)" = "$(as_admin_find -size +5M | sort)"

check all-logs "~/all-logs has a copy of every .log file" \
    test "$(ls "$HOME_DIR/all-logs" 2>/dev/null | sort)" = "$(as_admin_find -name '*.log' -printf '%f\n' | sort)"

check originals "The .log files are still where they were (copied, not moved)" \
    test "$(as_admin_find -name '*.log' | wc -l)" -eq 4

finish
