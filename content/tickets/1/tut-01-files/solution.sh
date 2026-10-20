# Reference solution, used by tests only. Runs as admin, like the player would.
set -euo pipefail
as_user admin "mkdir ~/notes \
  && cp ~/onboarding/welcome.txt ~/notes/ \
  && mv ~/notes/welcome.txt ~/notes/$CODEWORD.txt \
  && rm ~/onboarding/DELETE-ME.tmp \
  && touch ~/notes/done"
