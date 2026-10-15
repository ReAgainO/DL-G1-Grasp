#!/bin/bash
# Phase-2 driver: rerun the remaining frozen cells under rep_fixE, 16 lanes on cores 16..47.
set -uo pipefail
BASE=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_cfg
cd "$BASE"
[ -e pids/driver_phase2.pid ] && kill -0 "$(cat pids/driver_phase2.pid)" 2>/dev/null && { echo REFUSE_RUNNING; exit 4; }
echo $$ > pids/driver_phase2.pid
: > pids/phase2.launch.log
# remaining = jobs_phase2 minus the 5 already-run names
grep -v -E '^(a35_02_05|a35_10_10|d50_00_00|e35n_00_00|e35n_00_05)\|' jobs_phase2.txt > jobs_phase2_remaining.txt
wc -l jobs_phase2_remaining.txt >> pids/phase2.launch.log
i=0
while IFS="|" read -r n e x y f s; do
  while [ "$(pgrep -fc '[r]un_fixE.sh')" -ge 16 ]; do sleep 5; done
  c=$((16+(i%16)*2)); i=$((i+1))
  echo "launch $n cpu=$c,$((c+1))" >> pids/phase2.launch.log
  bash run_fixE.sh "$n" "$e" "$x" "$y" "$f" "$s" "$c,$((c+1))" >> pids/phase2.launch.log 2>&1 &
done < jobs_phase2_remaining.txt
wait
echo "PHASE2_DONE $(date -Is)" >> pids/phase2.launch.log
