# Fixed means: the job, run as sam, succeeds and writes today's report.
# Params: $OUTDIR
report="$OUTDIR/sales-$(date +%F).csv"
rm -f "$report"                     # only a report written by this check counts

check folder "$OUTDIR exists" \
    test -d "$OUTDIR"

check job-runs "The job runs as sam without errors" \
    runuser -u sam -- /usr/local/bin/nightly-report

check report "It wrote today's report" \
    grep -q "north,1204" "$report"

check not-wide-open "The folder isn't writable by everyone (no chmod 777 fixes!)" \
    test "$(( 0$(stat -c %a "$OUTDIR" 2>/dev/null) & 2 ))" -eq 0

finish
