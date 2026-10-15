#!/usr/bin/env bash
# Convert every candidate Kimodo clip into a staging stem and FK-probe it.
set -uo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
R="$B/harness_s1000/rep"
K="$B/kimodo100"
P=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
export MUJOCO_GL=disable PYTHONPATH="$R" TMPDIR="$R/tmp" XDG_CACHE_HOME="$R/cache"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p "$B/kimodo_conv"
cd "$R"

REACH_TEXT="A person reaches forward with their right hand to grab a small object on a table."
LIFT_TEXT="A standing person slowly lifts a small object upward with their right hand and keeps the left arm relaxed."

for s in reach_s43 reach_s7; do
  echo "=== convert $s (reach) ==="
  $P -B kimo2harness.py --npz "$K/$s.npz" --stem "$B/kimodo_conv/${s}_v2" --text "$REACH_TEXT" || exit 11
done
for s in lift_s42 lift_s7; do
  echo "=== convert $s (lift) ==="
  $P -B kimo2harness.py --npz "$K/$s.npz" --stem "$B/kimodo_conv/${s}_v2" --text "$LIFT_TEXT" || exit 12
done

echo
echo "########## FK probe vs cube ##########"
$P -B kimo_fk_probe.py "$R/out/wb_base_tpl/scene.xml" \
  "$B/kimodo_conv/reach_s43_v2.npz" "$B/kimodo_conv/reach_s7_v2.npz" \
  "$R/out/generated_phases2/reach_s43.npz" "$R/src/original_motions/near_s42.npz"
echo
echo "########## FK probe lift clips ##########"
$P -B kimo_fk_probe.py "$R/out/wb_base_tpl/scene.xml" \
  "$B/kimodo_conv/lift_s42_v2.npz" "$B/kimodo_conv/lift_s7_v2.npz" \
  "$R/out/generated_phases2/lift_s42.npz"
echo CONVERT_PROBE_DONE
