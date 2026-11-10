# Sam's report job writes into a folder that Sam "tidied away". Run it once
# as a real service, so its failure is in the journal for the player to find.
# Params: $OUTDIR
set -euo pipefail

id sam &>/dev/null || useradd -m -c "Sam, the intern" sam

cat > /usr/local/bin/nightly-report <<SCRIPT
#!/bin/bash
# Sam's nightly sales report. Runs as user sam.
out="$OUTDIR/sales-\$(date +%F).csv"
echo "Writing the sales report to \$out"
if ! printf 'region,sales\nnorth,1204\nsouth,980\n' > "\$out"; then
    echo "ERROR: cannot write \$out" >&2
    exit 1
fi
echo "Report done."
SCRIPT
chmod 755 /usr/local/bin/nightly-report

rm -rf "$OUTDIR"                                       # what Sam "tidied away"
systemctl reset-failed nightly-report.service &>/dev/null || true
systemd-run --quiet --unit=nightly-report --uid=sam --wait /usr/local/bin/nightly-report || true
