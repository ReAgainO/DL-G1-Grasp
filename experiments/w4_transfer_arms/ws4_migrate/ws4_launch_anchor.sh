#!/bin/bash
# ws4 step 05: launch ONE anchor cell (e35n_00_06) from own copy
set -uo pipefail
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base
L=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/logs
mkdir -p "$L"
echo "== pre-launch evidence: fresh out/ must be EMPTY =="
echo "out entries: $(ls -A "$DST/rep/out" | wc -l)  -> $(ls -A "$DST/rep/out")"
echo "raw entries: $(ls -A "$DST/raw" | wc -l)"
echo "anchor out dir exists? $([ -e "$DST/rep/out/e35n_00_06" ] && echo YES || echo NO)"
echo "now=$(date -Is)"
echo
cd "$DST" || exit 2
echo "== launch: bash run_fixE.sh e35n_00_06 35 0.266000 -0.127600 0 new_motion_cube_a_s42 70,71 =="
nohup bash run_fixE.sh e35n_00_06 35 0.266000 -0.127600 0 new_motion_cube_a_s42 70,71 \
  > "$L/anchor_e35n_00_06.launch.log" 2>&1 &
echo "launcher_pid=$!"
echo "$!" > "$L/anchor.pid"
sleep 20
echo "== 20s after launch: process state =="
ps -o pid,ppid,ni,psr,etime,cmd -p "$(cat "$L/anchor.pid")" 2>/dev/null
pgrep -af "[s]onic_grasp.py" | head -5
echo "-- launcher log so far --"
cat "$L/anchor_e35n_00_06.launch.log"
echo "-- meta file --"
cat "$DST/raw/e35n_00_06.meta.txt" 2>&1 | head -20
