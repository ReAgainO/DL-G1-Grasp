#!/usr/bin/env bash
# Closed-loop orchestration for the Kimodo-driven grasp.
#
#   install Kimodo reach -> src/original_motions/<reach_stem>.npz  (via N1_MOTION_STEM)
#   install Kimodo lift  -> out/generated_phases2/lift_s42.npz     (official clip backed up)
#   run the unmodified official sonic_grasp.py on the template scene
#   read the 20 gates, export the fixed-root 30 fps action CSV
#
# Usage: wb_loop.sh <reach_npz> <reach_stem> <lift_npz> <lift_stem> <run_name>
set -uo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
R="$B/harness_s1000/rep"
P=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
REACH_NPZ=${1:?}; REACH_STEM=${2:?}; LIFT_NPZ=${3:?}; LIFT_STEM=${4:?}; NAME=${5:?}

export MUJOCO_GL=disable PYTHONPATH="$R" TMPDIR="$R/tmp" XDG_CACHE_HOME="$R/cache"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd "$R"

echo "########## [1] convert Kimodo clips into the harness motion contract ##########"
$P -B kimo2harness.py --npz "$REACH_NPZ" --stem "$R/src/original_motions/$REACH_STEM" \
   --text "A person reaches forward with their right hand to grab a small object on a table." || exit 11
$P -B kimo2harness.py --npz "$LIFT_NPZ" --stem "$R/out/generated_phases2/$LIFT_STEM" \
   --text "A standing person slowly lifts a small object upward with their right hand and keeps the left arm relaxed." || exit 12

echo "########## [2] install the Kimodo lift into the phase-clip slot ##########"
BK="$R/out/official_phases2_backup"; mkdir -p "$BK"
for f in lift_s42.npz lift_s42.csv; do
  [ -e "$BK/$f" ] || cp -p "$R/out/generated_phases2/$f" "$BK/$f"
done
cp "$R/out/generated_phases2/$LIFT_STEM.npz" "$R/out/generated_phases2/lift_s42.npz"
cp "$R/out/generated_phases2/$LIFT_STEM.csv" "$R/out/generated_phases2/lift_s42.csv"
echo "reach_stem=$REACH_STEM  lift_slot=lift_s42 (from $LIFT_STEM)"
sha256sum "$R/src/original_motions/$REACH_STEM.npz" "$R/out/generated_phases2/lift_s42.npz" \
          "$R/out/official_phases2_backup/lift_s42.npz"

echo "########## [3] run the official harness (template scene, frozen flags) ##########"
bash "$B/run_cell.sh" "$NAME" 35 0.267 -0.118 0 "$REACH_STEM"
echo "run rc=$?"

echo "########## [4] gates ##########"
$P "$B/read_result.py" "$R/out/$NAME/result.json"

echo "########## [5] export fixed-root 30 fps action CSV ##########"
$P "$B/export_action_csv.py" "$R/out/$NAME/trajectory.npz" "$B/$NAME.action.csv" \
   --fps 30 --report "$B/$NAME.action.json"
echo LOOP_DONE
