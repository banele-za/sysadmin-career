# Reference solution, used by tests only. Runs as admin, like the player would.
set -euo pipefail
as_user admin "find $SHARE -name '$LOST' 2>/dev/null > ~/found.txt; \
  find $SHARE -size +5M 2>/dev/null > ~/big-files.txt; \
  mkdir ~/all-logs; find $SHARE -name '*.log' -exec cp {} ~/all-logs/ \; 2>/dev/null; true"
