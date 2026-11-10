# Eight years of shared drive: nested folders, files of every size, a few
# owners, one private folder (for the "Permission denied" lesson), and one
# lost file buried deep.
# Params: $HOME_DIR, $SHARE, $LOST
set -euo pipefail

rm -rf "$SHARE" "$HOME_DIR/found.txt" "$HOME_DIR/big-files.txt" "$HOME_DIR/all-logs"
for u in gary sam; do id "$u" &>/dev/null || useradd -m "$u"; done

dirs=(accounting/2019 accounting/2024/old accounting/2026 sales/clients/archive
      sales/presentations it/logs it/scripts/old hr/forms marketing/photos/events
      marketing/photos/2019/summer misc/do-not-delete misc/new-folder/new-folder)
for d in "${dirs[@]}"; do mkdir -p "$SHARE/$d"; done

touch_file() {   # touch_file PATH OWNER [SIZE]
    echo "content of $(basename "$1")" > "$1"
    [ -n "${3:-}" ] && truncate -s "$3" "$1"
    chown "$2:$2" "$1"
}
touch_file "$SHARE/accounting/2019/q1.xlsx"                    gary
touch_file "$SHARE/accounting/2024/old/budget.xlsx"            gary
touch_file "$SHARE/accounting/2026/forecast.xlsx"              gary 7M
touch_file "$SHARE/sales/clients/archive/northgate.txt"        sam
touch_file "$SHARE/sales/presentations/pitch-final.pptx"       sam 12M
touch_file "$SHARE/sales/presentations/pitch-final-v2.pptx"    sam 13M
touch_file "$SHARE/it/logs/printer.log"                        root
touch_file "$SHARE/it/logs/backup.log"                         root
touch_file "$SHARE/it/scripts/old/cleanup.log"                 root
touch_file "$SHARE/it/scripts/old/cleanup.sh"                  root
touch_file "$SHARE/hr/forms/holiday-request.txt"               root
touch_file "$SHARE/marketing/photos/events/party.jpg"          sam 3M
touch_file "$SHARE/marketing/photos/2019/summer/beach.jpg"     sam 6M
touch_file "$SHARE/misc/notes.txt"                             gary
touch_file "$SHARE/misc/new-folder/new-folder/install.log"     gary
touch_file "$SHARE/misc/do-not-delete/readme.txt"              root

# The lost file, four folders down where nobody would look.
lost_dir="$SHARE/marketing/photos/2019/summer"
[ "$LOST" = wifi-password.txt ] && lost_dir="$SHARE/misc/new-folder/new-folder"
[ "$LOST" = budget-FINAL-v2-really-final.xlsx ] && lost_dir="$SHARE/accounting/2024/old"
touch_file "$lost_dir/$LOST" gary

# Everyone may look around, except in HR's private folder.
chmod -R a+rX "$SHARE"
mkdir -p "$SHARE/hr/private"
touch_file "$SHARE/hr/private/salaries.xlsx" root
chmod 700 "$SHARE/hr/private"
