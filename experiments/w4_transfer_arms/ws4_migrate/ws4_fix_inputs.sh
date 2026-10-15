#!/bin/bash
# ws4 step 05b: add missing runtime INPUT cache from rep/out, quarantine failed attempt, re-run anchor
set -uo pipefail
SRC=/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base
L=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/logs
mkdir -p "$L"
echo "== [1] explicit out/ read-scan across the runtime import graph (sonic_grasp.py:8-33) =="
cd "$DST/rep" || exit 2
M="source_physics_core.py sonic_v11.py motion_input.py task_plan.py reference_filter.py policy_reference.py \
grasp_geometry.py discrete_reference.py adaptive_hand.py contact_audit.py decoded_arm_filter.py \
balance_audit.py table_placement.py finger_control.py setdown_plan.py neutral_pose.py \
execution_monitor.py clearance_approach.py motion_profile.py native_branch.py branch_execution.py \
cycle_latency.py branch_face_ik.py"
echo "modules scanned: $(echo $M | wc -w)"
grep -n "out/" $M 2>/dev/null | head -20
echo "-- (only sonic_grasp.py reads out/; other modules: no hits above) --"
echo
echo "== [2] preserve failed attempt-1 evidence =="
cp -a "$DST/raw/e35n_00_06.stdout.log" "$L/fail_attempt1_e35n_00_06.stdout.log"
cp -a "$DST/raw/e35n_00_06.meta.txt"   "$L/fail_attempt1_e35n_00_06.meta.txt"
mkdir -p "$DST/rep/out_broken_ws4"
[ -d "$DST/rep/out/e35n_00_06" ] && mv "$DST/rep/out/e35n_00_06" "$DST/rep/out_broken_ws4/e35n_00_06_attempt1" && echo "quarantined attempt1 out dir"
echo
echo "== [3] copy the required input cache from source rep/out (read-only source) =="
mkdir -p "$DST/rep/out"
cp -a "$SRC/rep/out/generated_phases2" "$DST/rep/out/"
cp -a "$SRC/rep/out/official-dynamics.json" "$SRC/rep/out/pinch-feasibility.json" "$DST/rep/out/"
du -sh "$DST/rep/out"; ls -la "$DST/rep/out/"
echo
echo "== [4] sha256 verify the added inputs vs source =="
for f in generated_phases2/lift_s42.npz generated_phases2/lift_s42.csv generated_phases2/hold_s42.npz \
         generated_phases2/hold_s42.csv generated_phases2/release_s42.npz generated_phases2/release_s42.csv \
         generated_phases2/summary.json generated_phases2/run.json generated_phases2/jobs.json \
         generated_phases2/generation.log official-dynamics.json pinch-feasibility.json; do
  a=$(sha256sum "$DST/rep/out/$f" 2>/dev/null | cut -d' ' -f1)
  b=$(sha256sum "$SRC/rep/out/$f" 2>/dev/null | cut -d' ' -f1)
  if [ -n "$a" ] && [ "$a" = "$b" ]; then echo "OK   $f  $a"; else echo "FAIL $f copy=$a src=$b"; fi
done
echo
echo "== [5] pre-relaunch state =="
echo "out entries now: $(ls -A "$DST/rep/out" | tr '\n' ' ')"
echo "anchor out dir exists? $([ -e "$DST/rep/out/e35n_00_06" ] && echo YES || echo NO)"
