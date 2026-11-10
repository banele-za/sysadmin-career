# Reference solution, used by tests only. Runs as admin, like the player would.
set -euo pipefail
as_user admin "grep ERROR ~/printer.log > ~/problems.txt; grep WARN ~/printer.log >> ~/problems.txt; \
  grep $SUSPECT ~/printer.log | wc -l > ~/$SUSPECT-count.txt; ls /root 2> ~/denied.txt || true"
