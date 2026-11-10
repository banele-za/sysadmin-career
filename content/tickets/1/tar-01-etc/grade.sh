# The archive must exist with the right ending, really be compressed with the
# asked-for method, and contain /etc, including root-only files.
# Params: $METHOD, $ARCHIVE
case "$METHOD" in
    gzip) file="$ARCHIVE.tar.gz"; tar_opt=-z; test_cmd="gzip -t" ;;
    xz)   file="$ARCHIVE.tar.xz"; tar_opt=-J; test_cmd="xz -t" ;;
esac
contents=$(tar $tar_opt -tf "$file" 2>/dev/null)

# in_archive NAME...: every NAME is listed in the archive.
in_archive() {
    local name
    for name in "$@"; do
        printf '%s\n' "$contents" | grep -qx "$name" || return 1
    done
}

check exists "$file exists" \
    test -f "$file"

check compressed "It really is $METHOD-compressed" \
    $test_cmd "$file"

check has-etc "It contains the /etc folder (etc/hosts, etc/passwd...)" \
    in_archive etc/hosts etc/passwd

check root-only "It includes root-only files too (etc/shadow): it was made with sudo" \
    in_archive etc/shadow

finish
