# Sam's laptop dump: photos, PDFs, junk .tmp files and one file to back up,
# all mixed together in one folder.
# Params: $HOME_DIR, $DUMP, $KEEP
set -euo pipefail

dump="$HOME_DIR/$DUMP"
rm -rf "$dump" "$HOME_DIR/backup"            # idempotent: start from scratch
mkdir -p "$dump"

for name in beach party-2019 cat cat-again receipt-scan; do
    echo "JPEG pretend image: $name" > "$dump/$name.jpg"
done
for name in cv tax-form manual-coffee-machine; do
    echo "PDF pretend document: $name" > "$dump/$name.pdf"
done
for name in cache-01 cache-02 download-partial; do
    echo "junk" > "$dump/$name.tmp"
done
echo "Sam's important file ($KEEP), please keep" > "$dump/$KEEP"
echo "Notes from the training day" > "$dump/notes.txt"     # stays where it is

chown -R admin:admin "$dump"
