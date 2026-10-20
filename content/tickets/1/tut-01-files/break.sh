# Set up the onboarding folder the mentor walks the player through.
# Params: $CODEWORD, $HOME_DIR
set -euo pipefail

onboarding="$HOME_DIR/onboarding"
rm -rf "$onboarding" "$HOME_DIR/notes"     # idempotent: start from scratch
mkdir -p "$onboarding/manuals"

cat > "$onboarding/welcome.txt" <<EOF
Welcome to the team!

Your login is "admin" and this server is srv01.
Ask the senior admin anything, and read the man pages.

Codeword: $CODEWORD
EOF

echo "temporary file, please delete" > "$onboarding/DELETE-ME.tmp"
echo "How to restart the coffee machine: unplug it." > "$onboarding/manuals/coffee.txt"

# Everything belongs to the player, so no sudo is needed for this ticket.
chown -R admin:admin "$onboarding"
