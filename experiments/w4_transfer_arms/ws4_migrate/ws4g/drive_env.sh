#!/usr/bin/env bash
# W4g ENV driver (<=2 slots, 2 cores each). jobs rows:
#   name|edge|cx|cy|face|stem|arm|grip
#   arm : off | env1 | env2   (ENVELOPE_COLLISION=0/1/2)
#   grip: path to grip-target JSON or "-" (none)
set -uo pipefail
M=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate
DST=$M/rep_ext_env
L=$M/logs
PYWS=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
JOBS=${1:?usage: drive_env.sh jobs_file [slots]}
SLOTS=${2:-2}
mkdir -p "$L"; PIDS="$L/env_pids_$(basename "$JOBS" .txt).txt"; touch "$PIDS"
alive() { local n=0 p; while read -r p; do [ -n "$p" ] && kill -0 "$p" 2>/dev/null && n=$((n+1)); done < "$PIDS"; echo "$n"; }
pick_cpus() { "$PYWS" "$M/ws4_idle.py" | awk '$1 ~ /^[0-9]+(\.[0-9]+)?$/ {c=$2; sub(/cpu/,"",c); printf "%s,", c}' | cut -d, -f1-2; }
while IFS='|' read -r name edge cx cy face stem arm grip; do
  [ -z "${name:-}" ] && continue
  while [ "$(alive)" -ge "$SLOTS" ]; do sleep 10; done
  CPUS=$(pick_cpus)
  ENVLVL=0; [ "$arm" = env1 ] && ENVLVL=1; [ "$arm" = env2 ] && ENVLVL=2
  GJ="${grip:-}"; [ "$GJ" = "-" ] && GJ=""
  if [ -n "$GJ" ]; then export GRIP_TARGET_JSON="$GJ"; else unset GRIP_TARGET_JSON || true; fi
  ( cd "$DST" && ENVELOPE_COLLISION=$ENVLVL W4G_ENV_GUARDS=1 \
    nohup bash run_fixE.sh "$name" "$edge" "$cx" "$cy" "$face" "$stem" "$CPUS" >> "$L/env.$arm.launch.log" 2>&1 & echo $! >> "$PIDS" )
  echo "launched $name arm=$arm envlvl=$ENVLVL grip=${GJ:-none} cpus=$CPUS at $(date +%T)"
done < "$JOBS"
echo "all launched; waiting"
while [ "$(alive)" -gt 0 ]; do sleep 15; done
echo "all done at $(date +%T)"
