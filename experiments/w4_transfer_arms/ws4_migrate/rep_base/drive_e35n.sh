#!/usr/bin/env bash
# Re-run the whole new-ARDY-reference stratum under the B-1 clock-consistency patch.
# Rationale: on the unpatched build these cells die with rc=1 and produce no result.json,
# so the sweep cannot quantify them. 20 lanes on cores 88..127 (the sweep owns 8..87).
set -uo pipefail
BASE=/data/group4/20261008-125638-qoder-d266d3a9/B1_clock
cd "$BASE"
export S_PY=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
[ -e pids/driver_e35n.pid ] && kill -0 "$(cat pids/driver_e35n.pid)" 2>/dev/null && { echo "REFUSE running"; exit 4; }
echo $$ > pids/driver_e35n.pid
i=0
: > pids/e35n.launch.log
while IFS="|" read -r n e x y f s; do
  case "$n" in e35n_00_00|e35n_04_00|e35n_08_04|e35n_12_08) continue;; esac
  while [ "$(pgrep -fc [r]un_b1.sh)" -ge 20 ]; do sleep 5; done
  c=$((88+(i%20)*2)); i=$((i+1))
  bash run_b1.sh "$n" "$e" "$x" "$y" "$f" "$s" "$c,$((c+1))" >> pids/e35n.launch.log 2>&1 &
done < jobs_e35n_all.txt
wait
echo "E35N_STRATUM_DONE $(date -Is)" >> pids/e35n.launch.log
