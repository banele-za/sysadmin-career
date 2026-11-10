# Reference solution, used by tests only. chpasswd sets a password without
# a prompt (the player types it into `passwd` instead).
set -euo pipefail
echo "$NEWHIRE:Welcome-to-Sales-1" | chpasswd
passwd -e "$NEWHIRE"
chage -M "$MAX_DAYS" "$NEWHIRE"
