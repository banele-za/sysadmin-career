# Reference solution, used by tests only. Runs as admin, like the player would.
set -euo pipefail
as_user admin "cd ~/$DUMP && mkdir photos docs && mv *.jpg photos/ && mv *.pdf docs/ \
  && rm *.tmp && mkdir ~/backup && cp $KEEP ~/backup/"
