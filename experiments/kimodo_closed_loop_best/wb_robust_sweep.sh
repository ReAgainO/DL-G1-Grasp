#!/usr/bin/env bash
# Robustness sweep for the Kimodo grasp pipeline.
#
# Goal: turn a single accepted cell into a real success-rate distribution by
# running every remaining Kimodo clip through the same 20-gate harness cell.
#
# Two independent sweeps (sequential on purpose: wb_loop3.sh stages the lift clip
# through the single shared path rep/out/generated_phases2/lift_s42.*, so
# concurrent runs would race):
#   A) lift sweep  : reach = accepted p6_conv, lift = l2/l3/l4/l5   -> wb_kimo_p6l2..l5
#   B) reach sweep : reach = p2..p5,            lift = OFFICIAL     -> wb_kimo_p2..p5
#
# p1 and p6 already have results; l1 already has a result. They are NOT rerun.
set -uo pipefail
D=/data/group4/20261008-232029-workbuddy-34e89f61
R="$D/harness_s1000/rep"
LOG="$D/robust_sweep.log"
export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache"
mkdir -p "$TMPDIR" "$D/cache"

echo "############ ROBUST SWEEP START $(date -u +%FT%TZ) ############" | tee -a "$LOG"
df -h /data | tail -1 | tee -a "$LOG"

# ---------- A) lift sweep on the accepted Kimodo reach ----------
for n in l2 l3 l4 l5; do
  echo "########## [A] lift ${n}_conv  $(date -u +%FT%TZ) ##########" | tee -a "$LOG"
  bash "$D/wb_loop3.sh" p6_conv "${n}_conv" "wb_kimo_p6${n}" >> "$LOG" 2>&1
  rc=$?
  echo "########## [A] lift ${n}_conv rc=$rc ##########" | tee -a "$LOG"
done

# ---------- B) reach sweep with the official lift ----------
for n in p2 p3 p4 p5; do
  echo "########## [B] reach ${n}_conv  $(date -u +%FT%TZ) ##########" | tee -a "$LOG"
  bash "$D/wb_loop3.sh" "${n}_conv" - "wb_kimo_${n}" >> "$LOG" 2>&1
  rc=$?
  echo "########## [B] reach ${n}_conv rc=$rc ##########" | tee -a "$LOG"
done

# ---------- summary ----------
echo "############ ROBUST SWEEP DONE $(date -u +%FT%TZ) ############" | tee -a "$LOG"
/home/group4/group4_dasc7606c/envs/kimodo/bin/python "$D/wb_robust_report.py" 2>&1 | tee -a "$LOG"
df -h /data | tail -1 | tee -a "$LOG"
echo "ROBUST_SWEEP_ALL_DONE"
