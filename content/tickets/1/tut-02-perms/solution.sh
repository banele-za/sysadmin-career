# Reference solution, used by tests only. Runs as admin, like the player would.
set -euo pipefail
as_user admin "chmod u+x '$LESSON/$SCRIPT' \
  && chmod 600 '$LESSON/$SECRET' \
  && sudo chown admin:'$GROUP' '$HANDOVER/report.txt'"
