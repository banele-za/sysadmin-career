# Reference solution, used by tests only.
set -euo pipefail
mkdir -p "$DEST"
find /srv /home/sam -user sam -type f -exec cp {} "$DEST"/ \;
