# Nothing to break: just make sure no backup exists yet.
# Params: $METHOD, $ARCHIVE
set -euo pipefail
rm -f "$ARCHIVE".tar*
rm -rf /root/backups
