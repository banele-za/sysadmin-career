# Plant last night's events in the logs:
#  - failed SSH logins in /var/log/secure (written like sshd writes them)
#  - a backup job that failed, in the systemd journal
# Params: $HOME_DIR, $BADUSER, $IP, $DISK
set -euo pipefail

rm -f "$HOME_DIR/intruder.txt" "$HOME_DIR/missing-disk.txt"

# authpriv messages go to /var/log/secure (see /etc/rsyslog.conf).
for port in 51234 51240 51262 51277 51301 51319; do
    logger -p authpriv.notice -t "sshd[$((port + 1000))]" \
        "Failed password for invalid user $BADUSER from $IP port $port ssh2"
done
logger -p authpriv.info -t "sshd[4410]" "Accepted publickey for admin from 10.0.2.2 port 40122 ssh2"
# rsyslog writes the file a moment later; wait until the lines are really there.
for _ in $(seq 1 50); do
    grep -q "invalid user $BADUSER from $IP port 51319" /var/log/secure && break
    sleep 0.1
done

# A real (temporary) systemd service that fails, so `journalctl -u` shows it.
systemctl reset-failed backup-job.service &>/dev/null || true
systemd-run --quiet --unit=backup-job --wait /bin/sh -c "
    echo 'Starting nightly backup of /srv'
    echo 'ERROR: backup target $DISK is not mounted'
    echo 'Backup aborted.'
    exit 1" || true
