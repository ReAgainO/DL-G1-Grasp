#!/usr/bin/env bash
# W4h W1S driver (<=2 slots, 2 cores each). jobs rows:
#   name|edge|cx|cy|face|stem|arm|grip|preset
#   arm : env0 | env1 | env2   (ENVELOPE_COLLISION=0/1/2)
#   grip: path to grip-target JSON or "-" (none)
#   preset: path to W4H_PRESET_JSON or "-" (none; then run is the untouched W4g arm)
#   extra: W4C_PHYS extra args appended by run_fixE.sh (e.g. "--freeze-close")
set -uo pipefail
M=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate
DST=$M/rep_ext_w1
L=$M/logs
PYWS=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
JOBS=${1:?usage: ws4h_drive.sh jobs_file [slots]}
SLOTS=${2:-2}
mkdir -p "$L"; PIDS="$L/w1s_pids_$(basename "$JOBS" .txt).txt"; touch "$PIDS"
alive() { local n=0 p; while read -r p; do [ -n "$p" ] && kill -0 "$p" 2>/dev/null && n=$((n+1)); done < "$PIDS"; echo "$n"; }
pick_cpus() { "$PYWS" "$M/ws4_idle.py" | awk '$1 ~ /^[0-9]+(\.[0-9]+)?$/ {c=$2; sub(/cpu/,"",c); printf "%s,", c}' | cut -d, -f1-2; }
while IFS='|' read -r name edge cx cy face stem arm grip preset extra; do
  [ -z "${name:-}" ] && continue
  while [ "$(alive)" -ge "$SLOTS" ]; do sleep 10; done
  CPUS=$(pick_cpus)
  ENVLVL=0; [ "$arm" = env1 ] && ENVLVL=1; [ "$arm" = env2 ] && ENVLVL=2
  GJ="${grip:-}"; [ "$GJ" = "-" ] && GJ=""
  PJ="${preset:-}"; [ "$PJ" = "-" ] && PJ=""
  if [ -n "$GJ" ]; then export GRIP_TARGET_JSON="$GJ"; else unset GRIP_TARGET_JSON || true; fi
  if [ -n "$PJ" ]; then export W4H_PRESET_JSON="$PJ"; else unset W4H_PRESET_JSON || true; fi
  if [ -n "${extra:-}" ]; then export W4C_PHYS="$extra"; else unset W4C_PHYS || true; fi
  ( cd "$DST" && ENVELOPE_COLLISION=$ENVLVL W4G_ENV_GUARDS=1 \
    nohup bash run_fixE.sh "$name" "$edge" "$cx" "$cy" "$face" "$stem" "$CPUS" >> "$L/w1s.$arm.launch.log" 2>&1 & echo $! >> "$PIDS" )
  echo "launched $name arm=$arm envlvl=$ENVLVL grip=${GJ:-none} preset=${PJ:-none} extra=${extra:-none} cpus=$CPUS at $(date +%T)"
done < "$JOBS"
echo "all launched; waiting"
while [ "$(alive)" -gt 0 ]; do sleep 15; done
echo "all done at $(date +%T)"
