# Gary's account: has a password, but locked, and expired as of yesterday.
# Params: $TEMP
set -euo pipefail
id gary &>/dev/null || useradd -m gary
echo "gary:Garys-Old-Password-1" | chpasswd
passwd -l gary >/dev/null                              # locked: "!" in front of the hash
chage -E "$(date -d yesterday +%F)" gary               # account expired yesterday
chage -d "$(date +%F)" gary                            # password itself is current
