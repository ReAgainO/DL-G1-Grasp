#!/usr/bin/env bash
# W4f driver for rep_ext_comb80 (<=2 slots, 2 cores each). jobs rows: name|edge|cx|cy|face|stem
set -uo pipefail
M=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate
DST=$M/rep_ext_comb80
L=$M/logs
PYWS=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
JOBS=${1:?usage: ws4f_drive.sh jobs_file}
SLOTS=${2:-2}
mkdir -p "$L"; PIDS="$L/ws4f_pids_$(basename "$JOBS" .txt).txt"; : > "$PIDS"
alive() { local n=0 p; while read -r p; do [ -n "$p" ] && kill -0 "$p" 2>/dev/null && n=$((n+1)); done < "$PIDS"; echo "$n"; }
pick_cpus() { "$PYWS" "$M/ws4_idle.py" | awk '$1 ~ /^[0-9]+(\.[0-9]+)?$/ {c=$2; sub(/cpu/,"",c); printf "%s,", c}' | cut -d, -f1-2; }
while IFS='|' read -r name edge cx cy face stem; do
  [ -z "${name:-}" ] && continue
  while [ "$(alive)" -ge "$SLOTS" ]; do sleep 10; done
  CPUS=$(pick_cpus)
  [[ "$CPUS" =~ ^[0-9]+,[0-9]+$ ]] || { echo "BAD CPUS=$CPUS"; exit 5; }
  ( cd "$DST" && FINGER_PD=100,10 FINGER_ARMATURE=0.1 \
    W4C_PHYS="--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10" W4C_TIMEOUT=2400 \
    nohup bash run_fixE.sh "$name" "$edge" "$cx" "$cy" "$face" "$stem" "$CPUS" </dev/null >> "$L/ws4f.comb.launch.log" 2>&1 & echo $! >> "$PIDS" )
  echo "launched $name cpus=$CPUS at $(date +%T)"
done < "$JOBS"
echo "all launched; waiting"
while [ "$(alive)" -gt 0 ]; do sleep 15; done
echo "all done at $(date +%T)"
