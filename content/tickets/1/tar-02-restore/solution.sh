# Reference solution, used by tests only.
set -euo pipefail
tar -xzf "$BACKUP" -C / "srv/accounting/$LOST"
