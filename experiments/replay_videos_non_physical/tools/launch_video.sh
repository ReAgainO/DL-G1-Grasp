#!/usr/bin/env bash
# Detach one replay render and return immediately, recording the real PID.
# Usage: launch_video.sh <episode> <cpu-pair>
# Note: the PID is recovered with pgrep instead of "$!" because "$!" got mangled by
# the upload path on the first version (the pid file ended up containing the literal
# two characters "$!"), which made the ledger evidence unusable. pgrep also proves the
# job actually started, which "$!" alone never did.
set -euo pipefail
T=/data/group4/20261009-132809-qoder-9b946d7f
EP=$1
CPUS=$2
mkdir -p "$T/videos" "$T/pids"
cd "$T"
setsid nohup env CPUS="$CPUS" bash "$T/tools/run_video.sh" "$EP" > "$T/videos/$EP.render.log" 2>&1 < /dev/null &
sleep 3
PID=$(pgrep -f "[q]2_video.py $EP" | head -1)
if [ -z "${PID:-}" ]; then
  echo "FAILED to start $EP; see $T/videos/$EP.render.log" >&2
  exit 1
fi
printf '%s\n' "$PID" > "$T/pids/$EP.pid"
echo "launched $EP pid=$PID cpus=$CPUS log=$T/videos/$EP.render.log"
