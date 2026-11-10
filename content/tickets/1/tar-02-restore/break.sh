# Last week's backup of /srv/accounting; since then Gary edited notes.txt
# (so the backup's copy is stale) and deleted one file.
# Params: $LOST, $BACKUP
set -euo pipefail

groupadd -f accounting
id gary &>/dev/null || useradd -m gary
usermod -aG accounting gary

rm -rf /srv/accounting /backups
mkdir -p /srv/accounting /backups
for f in ledger-2026.csv payroll-q4.csv vendors.csv; do
    printf 'id,item,amount\n1,%s,1000.00\n2,%s,2500.50\n' "$f" "$f" > "/srv/accounting/$f"
done
echo "Week 44: remember to chase Northgate." > /srv/accounting/notes.txt
chown -R gary:accounting /srv/accounting
chmod 640 /srv/accounting/*.csv

# The weekly backup (as root, so owners are recorded too).
tar -czf "$BACKUP" -C / srv/accounting
# Remember the lost file's content, so the grader can compare (root only).
sha256sum "/srv/accounting/$LOST" | cut -d' ' -f1 > /root/.lost-file.sha256

# A week passes: Gary's newer notes, then the accident.
echo "Week 45: Northgate paid! Also: new coffee machine order." >> /srv/accounting/notes.txt
rm "/srv/accounting/$LOST"
