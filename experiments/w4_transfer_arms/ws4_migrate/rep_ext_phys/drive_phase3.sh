#!/bin/bash
# Phase-3 driver (fixed): read 7 columns (S1000 format NAME|EDGE|X|Y|FACE|STEM|ORDER).
# Runs: 3 B1 controls + 12 ws2 cells under rep_fixE. 15 lanes on cores 48..77.
set -uo pipefail
BASE=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_phys
cd "$BASE"
[ -e pids/driver_phase3.pid ] && kill -0 "$(cat pids/driver_phase3.pid)" 2>/dev/null && { echo REFUSE_RUNNING; exit 4; }
echo $$ > pids/driver_phase3.pid
: > pids/phase3.launch.log
# free the names of cells whose fixE attempts crashed (partial out dirs)
for n in a35_02_05 a35_10_10 d50_00_00 a35_18_12 a35_19_12 a35_19_13 a35_19_14 a35_19_15 a35_19_16 a35_19_18 a35_19_19 d50_16_14 d50_16_15 d50_16_16 d50_16_17; do
  if [ -d "rep/out/$n" ] && [ ! -f "rep/out/$n/result.json" ]; then
    mkdir -p rep/out_broken_phase1
    mv "rep/out/$n" "rep/out_broken_phase1/$n"
    echo "quarantined partial dir: $n" >> pids/phase3.launch.log
  fi
done
i=0
while IFS="|" read -r n e x y f s o; do
  [ -z "$n" ] && continue
  while [ "$(pgrep -fc '[r]un_fixE.sh')" -ge 17 ]; do sleep 5; done
  c=$((48+(i%15)*2)); i=$((i+1))
  echo "launch $n cpu=$c,$((c+1)) stem=$s" >> pids/phase3.launch.log
  bash run_fixE.sh "$n" "$e" "$x" "$y" "$f" "$s" "$c,$((c+1))" >> pids/phase3.launch.log 2>&1 &
done < jobs_phase3.txt
wait
echo "PHASE3_DONE $(date -Is)" >> pids/phase3.launch.log
