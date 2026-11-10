# Reference solution, used by tests only. Runs as admin, like the player would.
# (man without a terminal just prints the page, so it's sent to /dev/null here.)
set -euo pipefail
as_user admin "man mkdir >/dev/null && mkdir -p ~/projects/$YEAR/$QUARTER && echo 6 > ~/home-field.txt"
