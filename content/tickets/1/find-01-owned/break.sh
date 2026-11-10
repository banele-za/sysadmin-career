# Sam's files, scattered through /srv and Sam's home, mixed with other
# people's files. Every file name is unique, so copying them all into one
# folder never overwrites anything.
# Params: $DEST
set -euo pipefail

rm -rf "$DEST" /srv/projects /srv/team-share
for u in sam gary; do id "$u" &>/dev/null || useradd -m "$u"; done
rm -rf /home/sam/drafts /home/sam/notes.txt

mkdir -p /srv/projects/website/img /srv/projects/sales-tool /srv/team-share/old /home/sam/drafts

make() {   # make PATH OWNER
    echo "$(basename "$1") made by $2" > "$1"
    chown "$2:$2" "$1"
}
make /srv/projects/website/index-draft.html       sam
make /srv/projects/website/img/logo-sam-v3.png     sam
make /srv/projects/website/style.css               gary
make /srv/projects/sales-tool/report-generator.sh  sam
make /srv/projects/sales-tool/config.ini           root
make /srv/team-share/meeting-notes-oct.txt         sam
make /srv/team-share/old/ideas-list.txt            sam
make /srv/team-share/budget.xlsx                   gary
make /home/sam/drafts/extension-letter.txt           sam
make /home/sam/notes.txt                           sam
