#!/usr/bin/env bash
# NAT2 orientation-authority sweep on the WORKING copy.
#
# Question: when the wrist orientation target is given real authority in
# APPROACH (the phase holding 56% of the twist), how far can we move it toward
# the clip's own orientation before the 20 gates break?
#
# Controls: ob=0.0 must reproduce the delivered pipeline EXACTLY (gates + metrics).
# Sequential (shared clip staging).  Delivered tree never written to.
set -uo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
R="$B/harness_nat2/rep"
C="$B/kimodo_conv"
BK="$R/out/official_phases2_backup"
D="$B/harness_nat2"
STEM=${STEM:-n4_conv}
TAG=${TAG:-n4}
LC=${LC:-l1_conv}
OB_LIST=${OB_LIST:-"0.0 0.25 0.5 0.75 1.0"}

export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache" MUJOCO_GL=disable
mkdir -p "$D/tmp" "$D/cache" "$R/tmp" "$R/cache" "$BK"
cp -p "$B/harness_s1000/.flags_flat" "$D/.flags_flat"
[ -e "$D/run_cell_nat2w.sh" ] || { echo "MISSING run_cell_nat2w.sh" >&2; exit 2; }
for f in lift_s42.npz lift_s42.csv; do
  [ -e "$BK/$f" ] || cp -p "$R/out/generated_phases2/$f" "$BK/$f"
done
cp "$C/$LC.npz" "$R/out/generated_phases2/lift_s42.npz"
cp "$C/$LC.csv" "$R/out/generated_phases2/lift_s42.csv"
cp "$C/$STEM.npz" "$R/src/original_motions/$STEM.npz"
cp "$C/$STEM.csv" "$R/src/original_motions/$STEM.csv"

echo "=== NAT2W ORIENTATION-AUTHORITY SWEEP ==="
echo "stem=$STEM lift=$LC ob_list=[$OB_LIST]"
echo "--- delivered tree (must stay 0e0435b6) ---"
sha256sum "$B/harness_s1000/rep/sonic_grasp.py"
echo "--- frozen archive (must stay 0e0435b6) ---"
sha256sum "$B/delivered_frozen_20261009/rep/sonic_grasp.py"
echo "--- working copy ---"
sha256sum "$R/sonic_grasp.py"
echo

for OB in $OB_LIST; do
  TAGV=$(printf '%s' "$OB" | tr -d '.')
  NAME="wb_nat4_${TAG}_o${TAGV}"
  echo "### $NAME (orient_blend=$OB) $(date -u +%FT%TZ)"
  bash "$D/run_cell_nat2w.sh" "$NAME" 35 0.267 -0.118 0 "$STEM" "$OB"
  echo "### $NAME rc=$? $(date -u +%FT%TZ)"
  echo
done

echo "=== NAT2W SWEEP DONE ==="
ls "$R/out" | grep wb_nat4 || true
