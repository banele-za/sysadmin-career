# The right answer, worked out independently with awk: column 3 is the
# customer, column 5 the status (any case). The player's file must hold
# exactly those lines, in the file's order.
# Params: $CUSTOMER, $CSV, $OUT, $COUNT_FILE
expected=$(awk -F, -v c="$CUSTOMER" '$3 == c && tolower($5) == "failed"' "$CSV")

check lines "$OUT has every failed $CUSTOMER invoice, and nothing else" \
    test "$(cat "$OUT" 2>/dev/null)" = "$expected"

check count "$COUNT_FILE has the number of those invoices" \
    test "$(tr -d '[:space:]' < "$COUNT_FILE" 2>/dev/null)" = "$(printf '%s\n' "$expected" | grep -c .)"

check csv-untouched "The billing log itself wasn't changed" \
    test "$(wc -l < "$CSV")" = 401

finish
