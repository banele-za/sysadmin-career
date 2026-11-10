# A small website folder to practise on.
# Params: $HOME_DIR, $SITE
set -euo pipefail

cd "$HOME_DIR"
rm -rf "$SITE" "$SITE".tar* restore
mkdir -p "$SITE/css" "$SITE/img" "$SITE/pages"
echo "<h1>Welcome to the $SITE</h1>" > "$SITE/index.html"
echo "body { font-family: sans-serif; }" > "$SITE/css/style.css"
for page in about contact holidays printer-faq; do
    # Repetitive text compresses well, so -z visibly shrinks the archive.
    # (A loop, not `yes | head`: under pipefail, `yes` being cut off counts as failure.)
    for _ in $(seq 400); do echo "<p>The $page page. The printer is not haunted.</p>"; done \
        > "$SITE/pages/$page.html"
done
head -c 20000 /dev/urandom > "$SITE/img/logo.png"
chown -R admin:admin "$SITE"
