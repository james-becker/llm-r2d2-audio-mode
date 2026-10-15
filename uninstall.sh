#!/bin/bash
# Remove R2D2 mode from Cursor and Codex. (Claude Code: /plugin uninstall r2d2@r2d2-mode)
HERE="$(cd "$(dirname "$0")" && pwd)"
python3 "$HERE/tools/hooks_config.py" uninstall
rm -rf "$HOME/.r2d2"
echo "R2 removed. Backups of your original hook files, if any, are at <file>.r2d2-backup."
