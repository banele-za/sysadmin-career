# Reference solution, used by tests only: find both answers in the logs, the
# way the player would, rather than copying them from the params.
set -euo pipefail
user=$(grep "Failed password" /var/log/secure | tail -n 1 | sed -E 's/.*invalid user ([^ ]+) from.*/\1/')
disk=$(journalctl -u backup-job --no-pager | grep -o '/mnt/[^ ]*' | tail -n 1)
as_user admin "echo $user > ~/intruder.txt; echo $disk > ~/missing-disk.txt"
