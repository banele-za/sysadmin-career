# Reference solution, used by tests only.
set -euo pipefail

chgrp -R "$GROUP" "$DIR"        # folder and existing reports -> shared group
chmod 2770 "$DIR"               # setgid: new files inherit the group; others out
chmod g+w "$DIR"/*              # existing reports were saved without group write

# RHEL 10 gives users umask 022 (new files rw-r--r--). 002 adds group write.
for u in $USERS; do
    echo "umask 002" >> "/home/$u/.bashrc"
done
