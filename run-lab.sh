#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME="${XDG_RUNTIME_DIR:-/tmp}"
PIDFILE="$RUNTIME/pipesay-lab.pid"
LAUNCH_STAMP="$RUNTIME/pipesay-lab.launch"
FORCE=0

_raise_window() {
  if command -v wmctrl >/dev/null 2>&1; then
    wmctrl -a "PipeSay Lab" 2>/dev/null || true
  fi
}

[[ "${1:-}" == "--restart" ]] && FORCE=1 && shift
[[ "${PIPSAY_RESTART:-}" == "1" ]] && FORCE=1

NOW=$(date +%s)
if [[ -f "$LAUNCH_STAMP" ]]; then
  last="$(tr -dc '0-9' < "$LAUNCH_STAMP" 2>/dev/null || echo 0)"
  if [[ -n "$last" ]] && (( NOW - last < 4 )); then
    FORCE=1
  fi
fi
printf '%s' "$NOW" > "$LAUNCH_STAMP"

if [[ -f "$PIDFILE" ]]; then
  old_pid="$(tr -dc '0-9' < "$PIDFILE")"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    if tr '\0' ' ' < "/proc/$old_pid/cmdline" 2>/dev/null | grep -q "dictation.py"; then
      if [[ "$FORCE" -eq 1 ]]; then
        kill "$old_pid" 2>/dev/null || true
        sleep 0.3
        kill -9 "$old_pid" 2>/dev/null || true
        rm -f "$PIDFILE"
      else
        kill -USR1 "$old_pid" 2>/dev/null
        _raise_window
        exit 0
      fi
    else
      kill "$old_pid" 2>/dev/null || true
      sleep 0.2
      rm -f "$PIDFILE"
    fi
  else
    rm -f "$PIDFILE"
  fi
fi

exec "$DIR/.venv/bin/python" "$DIR/dictation.py" "$@"
