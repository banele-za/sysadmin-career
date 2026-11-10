# Reference solution, used by tests only. Runs as admin, like the player would.
set -euo pipefail
as_user admin "cd ~ && tar -cf $SITE.tar $SITE && tar -czf $SITE.tar.gz $SITE \
  && mkdir restore && tar -xzf $SITE.tar.gz -C restore"
