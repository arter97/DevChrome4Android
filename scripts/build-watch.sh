#!/bin/bash
# Starts scripts/build.sh detached (unless one is running) and waits until it
# exits or the first step fails, then prints a summary.
# Usage: [VARIANT=official|release] scripts/build-watch.sh [ninja targets...]
ROOT=$(cd "$(dirname "$0")/.." && pwd)
L="$ROOT/logs/build.log"
PIDFILE="$ROOT/logs/build.pid"
mkdir -p "$ROOT/logs"
if ! { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }; then
  : > "$L"
  setsid nohup bash -c "\"$ROOT/scripts/build.sh\" \"\$@\" > \"$L\" 2>&1; echo EXIT=\$? >> \"$L\"" \
    _ "$@" >/dev/null 2>&1 &
  echo $! > "$PIDFILE"
fi
while ! grep -q "^EXIT=\|^FAILED" "$L"; do sleep 2; done
grep -m3 -A30 "^FAILED" "$L" | grep -v "^python3 \|clang++ " | cut -c1-400 | head -90
grep "^EXIT=" "$L" || tail -n1 "$L" | cut -c1-200
