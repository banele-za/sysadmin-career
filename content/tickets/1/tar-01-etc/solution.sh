# Reference solution, used by tests only.
set -euo pipefail
mkdir -p "$(dirname "$ARCHIVE")"
case "$METHOD" in
    gzip) tar -czf "$ARCHIVE.tar.gz" /etc 2>/dev/null ;;
    xz)   tar -cJf "$ARCHIVE.tar.xz" /etc 2>/dev/null ;;
esac
