#!/usr/bin/env bash
# 1) Archive the DELIVERED (successful) version into a frozen keep-safe directory.
#    This is a straight copy -- the delivery tree is never moved or modified.
# 2) Build a fresh WORKING copy (harness_nat2) for the natural-pose work.
#
# Delivered baseline that must stay intact:
#   BASE/harness_s1000/rep/sonic_grasp.py sha256
#     0e0435b66da9b9b5d56092246a0deda23c6b38fdac01f7d39e5a8496f14148b9
#   mtime 2026-10-08 06:31:21 +0800
set -euo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
SRC="$B/harness_s1000"
KEEP="$B/delivered_frozen_20261009"
W="$B/harness_nat2"

DELIVERED_SHA=0e0435b66da9b9b5d56092246a0deda23c6b38fdac01f7d39e5a8496f14148b9

echo "=== 0) verify delivered baseline BEFORE anything ==="
got=$(sha256sum "$SRC/rep/sonic_grasp.py" | cut -d' ' -f1)
printf 'delivered sonic_grasp.py = %s\n' "$got"
[ "$got" = "$DELIVERED_SHA" ] || { echo "ABORT: delivered hash mismatch" >&2; exit 9; }

echo
echo "=== 1) freeze-archive the delivered tree (copy only) ==="
if [ -e "$KEEP" ]; then
  echo "KEEP already exists -> verifying, not overwriting"
else
  cp -a "$SRC" "$KEEP"
  echo "copied $SRC -> $KEEP"
fi
sha256sum "$KEEP/rep/sonic_grasp.py"
cat > "$KEEP/FROZEN-README.txt" <<EOF
FROZEN ARCHIVE of the DELIVERED successful version.

Source tree      : $SRC
Archived at      : $(date -Iseconds)
sonic_grasp.py   : $DELIVERED_SHA
Delivered CSV    : $B/wb_deliverable/g1-rightcube-grasp-kimodo-30fps.csv
                   sha256 709fd544ce68c28feb57a2d8e61831824d9fc4254c70375c297254bf09b9eefd
Gates            : 20/20 (cell wb_kimo_p6l1)

This copy is READ-ONLY evidence. Do not edit it.
Active natural-pose work happens in harness_nat2/.
EOF
echo "wrote $KEEP/FROZEN-README.txt"

echo
echo "=== 2) fresh working copy for natural-pose work ==="
if [ -e "$W" ]; then
  echo "WARNING: $W already exists -> aborting to avoid clobbering it" >&2
  exit 3
fi
cp -a "$SRC" "$W"
cp -p "$SRC/.flags_flat" "$W/.flags_flat"
sha256sum "$W/rep/sonic_grasp.py"
echo "work copy ready: $W"

echo
echo "=== 3) re-verify delivered baseline AFTER copies ==="
sha256sum "$SRC/rep/sonic_grasp.py"
stat -c '%y %n' "$SRC/rep/sonic_grasp.py"
