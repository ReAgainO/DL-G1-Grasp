#!/usr/bin/env bash
# NAT2-BLEND sweep: how far can the grasp orientation move from the rollout t=0
# wrist pose toward the GENERATED clip orientation before the approach clock
# (26 s hard cap) is exceeded?
#
# Full clip orientation is 81.44 deg away from t=0 for p6_conv, which overflows.
# Sweep the geodesic blend t = 0.0..1.0 and find the largest t that still passes
# all 20 gates.  t=0 must reproduce the delivered pipeline exactly.
#
# Sequential (shared clip staging).  harness_s1000 (delivered) untouched.
set -uo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
R="$B/harness_nat/rep"
C="$B/kimodo_conv"
BK="$R/out/official_phases2_backup"
D="$B/harness_nat"
STEM=${STEM:-p6_conv}
TAG=${TAG:-p6}
LC=${LC:-l1_conv}
BLEND_LIST=${BLEND_LIST:-"0.0 0.1 0.2 0.35 0.5 0.75 1.0"}

export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache" MUJOCO_GL=disable
mkdir -p "$D/tmp" "$D/cache" "$R/tmp" "$R/cache" "$BK"
cp -p "$B/harness_s1000/.flags_flat" "$D/.flags_flat"
[ -e "$D/run_cell_nat2.sh" ] || { echo "MISSING run_cell_nat2.sh" >&2; exit 2; }
for f in lift_s42.npz lift_s42.csv; do
  [ -e "$BK/$f" ] || cp -p "$R/out/generated_phases2/$f" "$BK/$f"
done
cp "$C/$LC.npz" "$R/out/generated_phases2/lift_s42.npz"
cp "$C/$LC.csv" "$R/out/generated_phases2/lift_s42.csv"
cp "$C/$STEM.npz" "$R/src/original_motions/$STEM.npz"
cp "$C/$STEM.csv" "$R/src/original_motions/$STEM.csv"

echo "=== NAT2 BLEND SWEEP ==="
echo "stem=$STEM lift=$LC blends=[$BLEND_LIST]"
echo "--- delivered version (must stay 0e0435b6...) ---"
sha256sum "$B/harness_s1000/rep/sonic_grasp.py"
echo "--- experiment copy ---"
sha256sum "$R/sonic_grasp.py"
echo

for T in $BLEND_LIST; do
  TAGV=$(printf '%s' "$T" | tr -d '.')
  NAME="wb_nat3_${TAG}_b${TAGV}"
  echo "### $NAME (blend=$T) $(date -u +%FT%TZ)"
  bash "$D/run_cell_nat2.sh" "$NAME" 35 0.267 -0.118 0 "$STEM" on "$T"
  echo "### $NAME rc=$? $(date -u +%FT%TZ)"
  echo
done

echo "=== NAT2 BLEND SWEEP DONE ==="
ls "$R/out" | grep wb_nat3 || true
