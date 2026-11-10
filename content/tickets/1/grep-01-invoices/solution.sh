# Reference solution, used by tests only. Runs as admin, like the player would.
set -euo pipefail
as_user admin "grep '$CUSTOMER' $CSV | grep -i failed > $OUT; wc -l < $OUT > $COUNT_FILE"
