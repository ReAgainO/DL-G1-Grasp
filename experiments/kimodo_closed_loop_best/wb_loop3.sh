#!/usr/bin/env bash
# Isolation runs: swap in the Kimodo reach and/or the Kimodo lift independently.
#   RC = "-" -> keep the official reach (near_s42)
#   LC = "-" -> restore the official lift clip
# Usage: wb_loop3.sh <reach_conv_stem|-> <lift_conv_stem|-> <run_name>
set -uo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
R="$B/harness_s1000/rep"
C="$B/kimodo_conv"; BK="$R/out/official_phases2_backup"
P=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
RC=${1:?}; LC=${2:?}; NAME=${3:?}
mkdir -p "$BK"
for f in lift_s42.npz lift_s42.csv; do
  [ -e "$BK/$f" ] || cp -p "$R/out/generated_phases2/$f" "$BK/$f"
done

STEM="near_s42"
if [ "$RC" != "-" ]; then
  cp "$C/$RC.npz" "$R/src/original_motions/$RC.npz"
  cp "$C/$RC.csv" "$R/src/original_motions/$RC.csv"
  STEM="$RC"
fi
if [ "$LC" = "-" ]; then
  cp "$BK/lift_s42.npz" "$R/out/generated_phases2/lift_s42.npz"
  cp "$BK/lift_s42.csv" "$R/out/generated_phases2/lift_s42.csv"
  LSRC="OFFICIAL"
else
  cp "$C/$LC.npz" "$R/out/generated_phases2/lift_s42.npz"
  cp "$C/$LC.csv" "$R/out/generated_phases2/lift_s42.csv"
  LSRC="$LC"
fi
echo "run=$NAME reach_stem=$STEM lift=$LSRC"
sha256sum "$R/src/original_motions/$STEM.npz" "$R/out/generated_phases2/lift_s42.npz"
bash "$B/harness_s1000/run_cell.sh" "$NAME" 35 0.267 -0.118 0 "$STEM"
echo "run_cell rc=$?"
if [ -f "$R/out/$NAME/result.json" ]; then
  $P "$B/read_result.py" "$R/out/$NAME/result.json"
  $P "$B/export_action_csv.py" "$R/out/$NAME/trajectory.npz" "$B/$NAME.action.csv" --fps 30 --report "$B/$NAME.action.json"
else
  echo "NO result.json; stdout tail:"; tail -25 "$B/harness_s1000/raw/$NAME.stdout.log"
fi
echo ISOL_DONE
