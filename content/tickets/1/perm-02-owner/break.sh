# A project folder still owned by someone who left.
# Params: $LEAVER, $NEWOWNER, $TEAMMATE, $TEAM, $PROJECT, $DIR
set -euo pipefail

groupadd -f "$TEAM"
for u in "$LEAVER" "$NEWOWNER" "$TEAMMATE"; do
    id "$u" &>/dev/null || useradd -m "$u"
done
usermod -aG "$TEAM" "$NEWOWNER"
usermod -aG "$TEAM" "$TEAMMATE"
id gary &>/dev/null || useradd -m gary   # not in the team

rm -rf "$DIR"
mkdir -p "$DIR/drafts"
echo "Project plan for $PROJECT" > "$DIR/plan.txt"
echo "Budget: ask Gary" > "$DIR/budget.txt"
echo "First draft" > "$DIR/drafts/draft-1.txt"

# Everything belongs to the leaver and her private group, so the
# team gets nothing. Modes are already right for a team folder.
chown -R "$LEAVER:$LEAVER" "$DIR"
find "$DIR" -type d -exec chmod 750 {} +
find "$DIR" -type f -exec chmod 640 {} +
