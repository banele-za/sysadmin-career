# The lost file is back, identical and still Gary's; his newer notes survive;
# nothing got unpacked in the wrong place.
# Params: $LOST, $BACKUP
file="/srv/accounting/$LOST"

check restored "$file is back" \
    test -f "$file"

check identical "It's exactly the backed-up version" \
    test "$(sha256sum "$file" 2>/dev/null | cut -d' ' -f1)" = "$(cat /root/.lost-file.sha256)"

check owner "It still belongs to gary (group accounting)" \
    test "$(stat -c %U:%G "$file" 2>/dev/null)" = gary:accounting

check notes-kept "Gary's newer notes.txt wasn't overwritten by the old copy" \
    grep -q "Week 45" /srv/accounting/notes.txt

check no-stray "No stray copy unpacked in the wrong place (like ./srv/accounting)" \
    test "$(find / -xdev -path '*/srv/accounting' -type d -not -path /srv/accounting 2>/dev/null | wc -l)" -eq 0

finish
