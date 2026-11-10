# The billing system's invoice log: 400 CSV lines, four customers, statuses
# in inconsistent upper/lower case.
# Params: $CUSTOMER, $CSV, $OUT, $COUNT_FILE
set -euo pipefail

rm -f "$OUT" "$COUNT_FILE"
groupadd -f accounting
mkdir -p "$(dirname "$CSV")"

customers=("Northgate" "Bluefin" "Harrow & Sons" "Pemberton Ltd")
statuses=("PAID" "PAID" "paid" "PENDING" "FAILED" "PAID" "failed" "Paid" "Failed" "PAID" "PENDING")
{
    echo "invoice,date,customer,amount,status"
    for i in $(seq 1 400); do
        c=${customers[$(( (i * 5 + i / 7) % ${#customers[@]} ))]}
        s=${statuses[$(( (i * 3 + i / 4) % ${#statuses[@]} ))]}
        printf 'INV-%05d,2026-10-%02d,%s,%d.%02d,%s\n' $(( 10000 + i )) $(( i % 28 + 1 )) "$c" \
            $(( (i * 37) % 4000 + 50 )) $(( (i * 13) % 100 )) "$s"
    done
} > "$CSV"
chown root:accounting "$CSV"
chmod 644 "$CSV"
