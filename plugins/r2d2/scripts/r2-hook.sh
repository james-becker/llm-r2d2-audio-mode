#!/bin/bash
# R2D2 mode for coding agents.
# Usage: r2-hook.sh start|stop|stopped|error|alert|kill [claude|cursor|codex]   (hook JSON on stdin)
# Env: R2_VOLUME (thinking sparkle, default 0.15), R2_TALK_VOLUME (hello/finished/stop/alert, default 0.8),
#      R2_MUTE=1, R2_DEBUG_LOG=/path (append every hook payload)
# Copyright (c) 2026 James Becker. MIT License; see LICENSE.
ACTION=$1
AGENT=${2:-claude}
IN=$(cat)
[ -n "$R2_DEBUG_LOG" ] && printf '%s %s %s\n' "$AGENT" "$ACTION" "$IN" >> "$R2_DEBUG_LOG"

# Reply the way each agent expects: Cursor wants JSON from beforeSubmitPrompt and stop, Codex from Stop.
respond() {
  case "$AGENT:$1" in
    cursor:start) echo '{"continue": true}' ;;
    cursor:stop | codex:stop) echo '{}' ;;
  esac
}
trap "respond $ACTION" EXIT
[ -n "$R2_MUTE" ] && exit 0
DIR="$(cd "$(dirname "$0")" && pwd)"

# Pure-bash string field extraction (no interpreter startup on the hot path); empty for null or missing.
field() {
  local v="${IN#*\"$1\":}"
  [ "$v" = "$IN" ] && return
  v="${v#"${v%%[![:space:]]*}"}"
  case "$v" in \"*) v="${v#\"}"; printf '%s' "${v%%\"*}" ;; esac
}
# Codex runs hidden background sessions (e.g. memory updates) that fire hooks too; real sessions have a transcript.
[ "$AGENT" = codex ] && [ -z "$(field transcript_path)" ] && exit 0
SID=$(field session_id)
[ -n "$SID" ] || SID=$(field conversation_id)  # Cursor
BASE="${TMPDIR:-/tmp}/claude-r2-${SID:-default}"
LOUD="${R2_TALK_VOLUME:-0.8}"
alive() { [ -f "$BASE.pid" ] && kill -0 "$(cat "$BASE.pid")" 2>/dev/null; }

# Cursor reports how the turn ended on its stop hook.
if [ "$AGENT:$ACTION" = cursor:stop ]; then
  case "$(field status)" in
    aborted) ACTION=stopped ;;
    error) ACTION=error ;;
  esac
fi

# Resolve the real interpreter once; version-manager shims (pyenv, asdf) can add ~0.5s per launch.
pybin() {
  local cache="${TMPDIR:-/tmp}/claude-r2-python" py
  py=$(cat "$cache" 2>/dev/null)
  [ -x "$py" ] || { py=$(python3 -c 'import sys; print(sys.executable)') && echo "$py" > "$cache"; }
  echo "$py"
}

# Hand an ending to the running babble so sounds never overlap; play it directly if nothing is running.
finish_with() { # flag phrase
  if alive; then touch "$BASE.$1"; else "$(pybin)" "$DIR/r2.py" "$2" --vol "$LOUD" >/dev/null 2>&1; fi
}

case "$ACTION" in
  start)
    alive && kill "$(cat "$BASE.pid")"
    rm -f "$BASE.finish" "$BASE.stopped" "$BASE.error" "$BASE.alert"
    "$(pybin)" "$DIR/r2.py" babble --state "$BASE" --transcript "$(field transcript_path)" \
      --vol "${R2_VOLUME:-0.15}" --talk-vol "$LOUD" </dev/null >/dev/null 2>&1 &
    echo $! > "$BASE.pid"
    disown
    ;;
  stop)    finish_with finish finished ;;
  stopped) finish_with stopped stopped ;;
  error)   finish_with error sad ;;
  alert)   if alive; then touch "$BASE.alert"; else "$(pybin)" "$DIR/r2.py" alert --vol 0.7 >/dev/null 2>&1; fi ;;
  kill)  # session ended: let a queued ending play out (codex exec ends the session right after Stop)
    [ -f "$BASE.finish" ] || [ -f "$BASE.stopped" ] || [ -f "$BASE.error" ] || { alive && kill "$(cat "$BASE.pid")"; } ;;
esac
exit 0
