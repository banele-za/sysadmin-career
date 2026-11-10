# Gary's monthly report, with nowhere to link it from yet.
# Params: $MONTH, $REPORT, $SHORTCUT, $SAFETY
set -euo pipefail

groupadd -f accounting
id gary &>/dev/null || useradd -m gary
usermod -aG accounting gary

rm -rf /srv/accounting/reports /srv/accounting/archive
rm -f "$SHORTCUT"
mkdir -p /srv/accounting/reports /srv/accounting/archive
chown root:accounting /srv/accounting /srv/accounting/reports /srv/accounting/archive
chmod 775 /srv/accounting/reports /srv/accounting/archive

printf 'Month,Total\n%s,98112.40\n' "$MONTH" > "$REPORT"
chown gary:accounting "$REPORT"
chmod 664 "$REPORT"
