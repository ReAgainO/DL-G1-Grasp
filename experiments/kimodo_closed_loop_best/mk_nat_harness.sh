#!/usr/bin/env bash
# Create a work copy of the harness for the "natural grasp" experiment.
#
# The original rep/ is NEVER modified (its sonic_grasp.py sha must stay
# 0e0435b6... so every earlier result stays reproducible). We copy it to
# rep_nat/ and patch only that copy.
set -euo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
SRC="$B/harness_s1000/rep"
DST="$B/harness_nat/rep"

mkdir -p "$B/harness_nat"
if [ -e "$DST" ]; then
  echo "REFUSE: $DST exists"
  exit 3
fi
cp -a "$SRC" "$DST"
echo "copied $SRC -> $DST"
sha256sum "$DST/sonic_grasp.py"
echo "--- out/ dirs are symlink-free copies; keep only what we need ---"
du -sh "$DST"
echo COPY_DONE
