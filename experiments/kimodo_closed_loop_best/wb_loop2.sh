#!/usr/bin/env bash
# Closed loop, step 2: install already-converted Kimodo clips and run.
#
#   reach -> src/original_motions/<stem>.{npz,csv}   (selected via N1_MOTION_STEM)
#   lift  -> out/generated_phases2/lift_s42.{npz,csv} (official clip backed up once)
#   run the UNMODIFIED official sonic_grasp.py, template scene, frozen flags
#   read the 20 gates, export the fixed-root 30 fps action CSV
#
# Usage: wb_loop2.sh <reach_conv_stem> <lift_conv_stem> <run_name>
set -uo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
R="$B/harness_s1000/rep"
C="$B/kimodo_conv"
P=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
RC=${1:?reach conv stem}; LC=${2:?lift conv stem}; NAME=${3:?run name}

echo "########## [1] install reach=$RC  lift(src)=$LC ##########"
cp "$C/$RC.npz" "$R/src/original_motions/$RC.npz"
cp "$C/$RC.csv" "$R/src/original_motions/$RC.csv"
BK="$R/out/official_phases2_backup"; mkdir -p "$BK"
for f in lift_s42.npz lift_s42.csv; do
  [ -e "$BK/$f" ] || cp -p "$R/out/generated_phases2/$f" "$BK/$f"
done
cp "$C/$LC.npz" "$R/out/generated_phases2/lift_s42.npz"
cp "$C/$LC.csv" "$R/out/generated_phases2/lift_s42.csv"
sha256sum "$R/src/original_motions/$RC.npz" "$R/out/generated_phases2/lift_s42.npz" \
          "$BK/lift_s42.npz" "$C/$LC.npz"

echo "########## [2] run official harness ##########"
bash "$B/harness_s1000/run_cell.sh" "$NAME" 35 0.267 -0.118 0 "$RC"
echo "run_cell rc=$?"

echo "########## [3] gates ##########"
[ -f "$R/out/$NAME/result.json" ] && $P "$B/read_result.py" "$R/out/$NAME/result.json" \
  || { echo "NO result.json; stdout tail:"; tail -30 "$R/../raw/$NAME.stdout.log"; }

echo "########## [4] export fixed-root 30 fps action CSV ##########"
if [ -f "$R/out/$NAME/trajectory.npz" ]; then
  $P "$B/export_action_csv.py" "$R/out/$NAME/trajectory.npz" "$B/$NAME.action.csv" \
     --fps 30 --report "$B/$NAME.action.json"
fi
echo LOOP2_DONE
