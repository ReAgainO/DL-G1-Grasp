#!/usr/bin/env bash
# W4c A/B launcher: <=2 concurrent cells, own pid bookkeeping (never counts other
# workers' run_fixE.sh). jobs file rows: name|edge|cx|cy|face|stem|arm|cpus
# arm == phys  -> sets W4C_PHYS (the official-recipe translation); arm == base -> unset
set -uo pipefail
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_phys
L=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/logs
JOBS=${1:?usage: ws4c_drive.sh jobs_file}
SLOTS=${2:-2}
PHYS_ARGS=${W4C_PHYS_ARGS:---substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10}
mkdir -p "$L"; PIDS="$L/ws4c_pids.txt"; touch "$PIDS"
alive() { local n=0 p; while read -r p; do [ -n "$p" ] && kill -0 "$p" 2>/dev/null && n=$((n+1)); done < "$PIDS"; echo "$n"; }
while IFS='|' read -r name edge cx cy face stem arm cpus; do
  [ -z "${name:-}" ] && continue
  while [ "$(alive)" -ge "$SLOTS" ]; do sleep 10; done
  if [ "$arm" = "phys" ]; then
    ( cd "$DST" && W4C_PHYS="$PHYS_ARGS" W4C_TIMEOUT="${W4C_TIMEOUT:-2400}" \
      nohup bash run_fixE.sh "$name" "$edge" "$cx" "$cy" "$face" "$stem" "$cpus" \
      >> "$L/ws4c.$arm.launch.log" 2>&1 & echo $! >> "$PIDS" )
  else
    ( cd "$DST" && W4C_TIMEOUT="${W4C_TIMEOUT:-2400}" \
      nohup bash run_fixE.sh "$name" "$edge" "$cx" "$cy" "$face" "$stem" "$cpus" \
      >> "$L/ws4c.$arm.launch.log" 2>&1 & echo $! >> "$PIDS" )
  fi
  echo "launched $name arm=$arm cpus=$cpus at $(date +%T)"
done < "$JOBS"
echo "all launches issued; waiting for stragglers"
while [ "$(alive)" -gt 0 ]; do sleep 15; done
echo "all done at $(date +%T)"
