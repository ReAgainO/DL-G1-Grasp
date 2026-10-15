#!/usr/bin/env bash
# W4c follow-up launcher (ablation/attribution arms). Same slot bookkeeping as ws4c_drive.sh.
# jobs file rows: name|edge|cx|cy|face|stem|arm|cpus
#   arm = base  -> no physics knobs (bit-identical baseline path)
#         phys  -> all four knobs (canonical M2 translation)
#         sub4  -> --substep 4 only
#         soft  -> --contact-margin 0.001 --solref 0.02 1 --impratio 10 (no substep)
set -uo pipefail
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_phys
L=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/logs
JOBS=${1:?usage: ws4c_drive2.sh jobs_file}
SLOTS=${2:-2}
mkdir -p "$L"; PIDS="$L/ws4c_pids2.txt"; touch "$PIDS"
alive() { local n=0 p; while read -r p; do [ -n "$p" ] && kill -0 "$p" 2>/dev/null && n=$((n+1)); done < "$PIDS"; echo "$n"; }
case "$0" in *) :;; esac
case_args() {
  case "$1" in
    base) echo "" ;;
    phys) echo "--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10" ;;
    sub4) echo "--substep 4" ;;
    soft) echo "--contact-margin 0.001 --solref 0.02 1 --impratio 10" ;;
    *) echo "BAD_ARM" ;;
  esac
}
while IFS='|' read -r name edge cx cy face stem arm cpus; do
  [ -z "${name:-}" ] && continue
  ARGS=$(case_args "$arm")
  [ "$ARGS" = "BAD_ARM" ] && { echo "unknown arm $arm"; exit 4; }
  while [ "$(alive)" -ge "$SLOTS" ]; do sleep 10; done
  ( cd "$DST" && W4C_PHYS="$ARGS" W4C_TIMEOUT="${W4C_TIMEOUT:-2400}" \
    nohup bash run_fixE.sh "$name" "$edge" "$cx" "$cy" "$face" "$stem" "$cpus" \
    >> "$L/ws4c.$arm.launch.log" 2>&1 & echo $! >> "$PIDS" )
  echo "launched $name arm=$arm args='$ARGS' cpus=$cpus at $(date +%T)"
done < "$JOBS"
echo "all launched; waiting"
while [ "$(alive)" -gt 0 ]; do sleep 15; done
echo "all done at $(date +%T)"
