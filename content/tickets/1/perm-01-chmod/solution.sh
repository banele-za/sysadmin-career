# Reference solution, used by tests only.
set -euo pipefail
chmod 640 "$DIR/$REPORT"            # rw- r-- ---
chmod 744 "$DIR/$SCRIPT"            # rwx r-- r--
