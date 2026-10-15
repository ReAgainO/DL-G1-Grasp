#!/usr/bin/env bash
# NAT-EXP 2 sweep: does taking the grasp orientation from the GENERATED clip
# (instead of the rollout t=0 wrist pose) produce a natural pose that still
# passes all 20 gates?
#
# Matrix (sequential -- shared clip staging paths would race):
#   clip x7_conv  orient=off   -> control (must reproduce the delivered pipeline)
#   clip x7_conv  orient=on    -> treatment
#   clip n4_conv  orient=off   -> control on the natural-prompt clip
#   clip n4_conv  orient=on    -> treatment on the natural-prompt clip
#
# harness_s1000 (the delivered, successful version) is never written to.
set -uo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
R="$B/harness_nat/rep"
C="$B/kimodo_conv"
BK="$R/out/official_phases2_backup"
D="$B/harness_nat"
LC=${LC:-l1_conv}

export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache" MUJOCO_GL=disable
mkdir -p "$D/tmp" "$D/cache" "$R/tmp" "$R/cache" "$BK"

cp -p "$B/harness_s1000/.flags_flat" "$D/.flags_flat"
[ -e "$D/run_cell_nat2.sh" ] || { echo "MISSING run_cell_nat2.sh" >&2; exit 2; }

for f in lift_s42.npz lift_s42.csv; do
  [ -e "$BK/$f" ] || cp -p "$R/out/generated_phases2/$f" "$BK/$f"
done
cp "$C/$LC.npz" "$R/out/generated_phases2/lift_s42.npz"
cp "$C/$LC.csv" "$R/out/generated_phases2/lift_s42.csv"

echo "=== NAT2 SWEEP ==="
echo "lift=$LC"
echo "--- delivered version untouched? ---"
sha256sum "$B/harness_s1000/rep/sonic_grasp.py"
echo "--- experiment copy ---"
sha256sum "$R/sonic_grasp.py"
echo

run_pair() {
  local STEM="$1" TAG="$2"
  for MODE in off on; do
    local NAME="wb_nat2_${TAG}_${MODE}"
    cp "$C/$STEM.npz" "$R/src/original_motions/$STEM.npz"
    cp "$C/$STEM.csv" "$R/src/original_motions/$STEM.csv"
    echo "### $NAME (stem=$STEM orient=$MODE) $(date -u +%FT%TZ)"
    bash "$D/run_cell_nat2.sh" "$NAME" 35 0.267 -0.118 0 "$STEM" "$MODE"
    echo "### $NAME rc=$? $(date -u +%FT%TZ)"
    echo
  done
}

run_pair p6_conv p6
run_pair n4_conv n4

echo "=== NAT2 SWEEP DONE ==="
ls "$R/out" | grep wb_nat2 || true
