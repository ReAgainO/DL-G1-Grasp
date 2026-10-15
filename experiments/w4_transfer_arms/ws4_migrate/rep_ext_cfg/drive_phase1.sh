#!/bin/bash
# Phase-1 validation driver for rep_fixE: 6 cells (3 controls + 2 frozen + 1 near-miss).
set -uo pipefail
BASE=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_cfg
cd "$BASE"
[ -e pids/driver_phase1.pid ] && kill -0 "$(cat pids/driver_phase1.pid)" 2>/dev/null && { echo REFUSE_RUNNING; exit 4; }
echo $$ > pids/driver_phase1.pid
: > pids/phase1.launch.log
i=0
while IFS="|" read -r n e x y f s; do
  c=$((16+2*i)); i=$((i+1))
  echo "launch $n cpu=$c,$((c+1))" >> pids/phase1.launch.log
  bash run_fixE.sh "$n" "$e" "$x" "$y" "$f" "$s" "$c,$((c+1))" >> pids/phase1.launch.log 2>&1 &
done < jobs_phase1.txt
wait
echo "PHASE1_DONE $(date -Is)" >> pids/phase1.launch.log
