# player-shell.sh: installed by the game as /etc/profile.d/sysadmin-game.sh
# before every ticket. Login shells (the player's terminal) read it.
#
# Reading documentation earns a small XP bonus (the design doc's "man pages
# first"). These wrappers only leave a marker file that the game looks for
# when you submit; the real man and info then run exactly as usual.

_sysadmin_game_read_docs() { : > /tmp/.sysadmin-game-read-docs 2>/dev/null; }
man()  { _sysadmin_game_read_docs; command man "$@"; }
info() { _sysadmin_game_read_docs; command info "$@"; }
