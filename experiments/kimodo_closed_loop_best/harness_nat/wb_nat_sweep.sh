#!/usr/bin/env bash
# NAT-EXP sweep driver.
# Stages the ACCEPTED Kimodo reach (p6_conv) + ACCEPTED Kimodo lift (l1_conv)
# into the task-owned PATCHED harness copy (harness_nat/rep) and sweeps
# --flat-pinch-relax K.  harness_s1000 is never written to.
#
# Sequential by construction: every cell stages the same two clip paths, so
# parallel runs would race (same reason documented in wb_lift_sweep.sh).
set -uo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
R="$B/harness_nat/rep"
C="$B/kimodo_conv"
BK="$R/out/official_phases2_backup"
D="$B/harness_nat"
P=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
RC=${RC:-p6_conv}
LC=${LC:-l1_conv}
RELAX_LIST=${RELAX_LIST:-"1.0 0.6 0.4 0.2 0.0"}

export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache" MUJOCO_GL=disable
mkdir -p "$D/tmp" "$D/cache" "$R/tmp" "$R/cache" "$BK"

# frozen flag list -- byte-identical to the controlled S1000 experiments
cp -p "$B/harness_s1000/.flags_flat" "$D/.flags_flat"
[ -e "$D/run_cell_nat.sh" ] || { echo "MISSING run_cell_nat.sh" >&2; exit 2; }

# refresh the official-lift backup so the staged lift can always be restored
for f in lift_s42.npz lift_s42.csv; do
  [ -e "$BK/$f" ] || cp -p "$R/out/generated_phases2/$f" "$BK/$f"
done

# stage the clips (once; they are reused by every cell)
cp "$C/$RC.npz" "$R/src/original_motions/$RC.npz"
cp "$C/$RC.csv" "$R/src/original_motions/$RC.csv"
cp "$C/$LC.npz" "$R/out/generated_phases2/lift_s42.npz"
cp "$C/$LC.csv" "$R/out/generated_phases2/lift_s42.csv"

echo "=== NAT SWEEP ==="
echo "reach=$RC lift=$LC relax_list=[$RELAX_LIST]"
echo "--- staged sha256 ---"
sha256sum "$R/src/original_motions/$RC.npz" "$R/out/generated_phases2/lift_s42.npz"
echo "--- flag list sha ---"
sha256sum "$D/.flags_flat"
echo "--- sonic_grasp sha ---"
sha256sum "$R/sonic_grasp.py"
echo

for K in $RELAX_LIST; do
  TAG=$(printf '%s' "$K" | tr -d '.')
  NAME="wb_nat_r${TAG}"
  echo "### $NAME (relax=$K) $(date -u +%FT%TZ)"
  bash "$D/run_cell_nat.sh" "$NAME" 35 0.267 -0.118 0 "$RC" "$K"
  echo "### $NAME rc=$? $(date -u +%FT%TZ)"
  echo
done

echo "=== NAT SWEEP DONE ==="
ls -la "$R/out" | grep wb_nat_r || true
