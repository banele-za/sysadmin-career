# Grade the tar tutorial: two archives with the folder inside, and a restore.
# Params: $HOME_DIR, $SITE
cd "$HOME_DIR"

check tar "~/$SITE.tar contains the $SITE folder" \
    sh -c "tar -tf '$SITE.tar' | grep -q '^$SITE/pages/about.html$'"

check tar-gz "~/$SITE.tar.gz is gzip-compressed and contains the folder" \
    sh -c "gzip -t '$SITE.tar.gz' && tar -tzf '$SITE.tar.gz' | grep -q '^$SITE/pages/about.html$'"

check smaller "The .tar.gz is smaller than the .tar" \
    test "$(stat -c %s "$SITE.tar.gz" 2>/dev/null || echo 0)" -lt "$(stat -c %s "$SITE.tar" 2>/dev/null || echo 0)"

check restored "~/restore/$SITE matches the original folder" \
    diff -r "$SITE" "restore/$SITE"

finish
