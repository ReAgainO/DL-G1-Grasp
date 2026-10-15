#!/usr/bin/env bash
# W4e driver (<=2 slots, 2 cores each). jobs rows: name|edge|cx|cy|face|stem|arm
#   arm=off  : no env (both switches off, must reproduce the W4a baseline)
#   arm=comb : FINGER_PD=100,10 FINGER_ARMATURE=0.1 W4C_PHYS="--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10"
set -uo pipefail
M=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate
DST=$M/rep_ext_comb
L=$M/logs
PYWS=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
JOBS=${1:?usage: ws4e_drive.sh jobs_file}
SLOTS=${2:-2}
mkdir -p "$L"; PIDS="$L/ws4e_pids_$(basename "$JOBS" .txt).txt"; touch "$PIDS"
alive() { local n=0 p; while read -r p; do [ -n "$p" ] && kill -0 "$p" 2>/dev/null && n=$((n+1)); done < "$PIDS"; echo "$n"; }
pick_cpus() { "$PYWS" "$M/ws4_idle.py" | awk '$1 ~ /^[0-9]+(\.[0-9]+)?$/ {c=$2; sub(/cpu/,"",c); printf "%s,", c}' | cut -d, -f1-2; }
while IFS='|' read -r name edge cx cy face stem arm; do
  [ -z "${name:-}" ] && continue
  while [ "$(alive)" -ge "$SLOTS" ]; do sleep 10; done
  CPUS=$(pick_cpus)
  if [ "$arm" = comb ]; then
    ( cd "$DST" && FINGER_PD=100,10 FINGER_ARMATURE=0.1 \
      W4C_PHYS="--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10" \
      nohup bash run_fixE.sh "$name" "$edge" "$cx" "$cy" "$face" "$stem" "$CPUS" >> "$L/ws4e.comb.launch.log" 2>&1 & echo $! >> "$PIDS" )
  elif [ "$arm" = off ]; then
    ( cd "$DST" && nohup bash run_fixE.sh "$name" "$edge" "$cx" "$cy" "$face" "$stem" "$CPUS" >> "$L/ws4e.off.launch.log" 2>&1 & echo $! >> "$PIDS" )
  else
    echo "unknown arm $arm"; exit 4
  fi
  echo "launched $name arm=$arm cpus=$CPUS at $(date +%T)"
done < "$JOBS"
echo "all launched; waiting"
while [ "$(alive)" -gt 0 ]; do sleep 15; done
echo "all done at $(date +%T)"
