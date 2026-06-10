#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="${XDG_RUNTIME_DIR:-/tmp}/pipesay.pid"

if [[ -f "$PIDFILE" ]]; then
  old_pid="$(tr -dc '0-9' < "$PIDFILE")"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    if tr '\0' ' ' < "/proc/$old_pid/cmdline" 2>/dev/null | grep -q "dictation.py"; then
      kill -USR1 "$old_pid" 2>/dev/null
      exit 0
    fi
    kill "$old_pid" 2>/dev/null || true
    sleep 0.2
  fi
  rm -f "$PIDFILE"
fi

exec "$DIR/.venv/bin/python" "$DIR/dictation.py" "$@"
