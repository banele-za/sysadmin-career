# Reference solution, used by tests only.
set -euo pipefail
passwd -u gary
chage -E -1 gary
echo "gary:$TEMP" | chpasswd
passwd -e gary
