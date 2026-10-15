#!/bin/bash
# Install R2D2 mode for Cursor and/or Codex. (Claude Code: install the plugin instead; see README.)
# Usage: ./install.sh [cursor] [codex]     default: whichever of them is installed
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.r2d2"

agents="$*"
if [ -z "$agents" ]; then
  [ -d "$HOME/.cursor" ] && agents="cursor"
  [ -d "$HOME/.codex" ] && agents="$agents codex"
fi
[ -n "$agents" ] || { echo "Neither Cursor (~/.cursor) nor Codex (~/.codex) found. Usage: ./install.sh [cursor] [codex]"; exit 1; }
command -v python3 >/dev/null || { echo "R2 needs python3."; exit 1; }

mkdir -p "$DEST"
cp "$HERE/plugins/r2d2/scripts/r2.py" "$HERE/plugins/r2d2/scripts/r2-hook.sh" "$DEST/"
chmod +x "$DEST/r2.py" "$DEST/r2-hook.sh"
echo "Installed R2 to $DEST"
python3 "$HERE/tools/hooks_config.py" install "$DEST/r2-hook.sh" $agents

case " $agents " in *" codex "*)
  echo
  echo "Codex: hooks must be trusted before they run. Start codex, type /hooks, and trust the r2-hook.sh entries." ;;
esac
echo "Done. Say hi to R2 in a new session. 🤖"
