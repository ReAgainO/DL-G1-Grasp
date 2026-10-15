#!/usr/bin/env bash
# NAT2 runner: points at the WORKING copy harness_nat2 (patched orientation servo).
# harness_s1000 (delivered) and delivered_frozen_20261009 are never written to.
#
# usage: run_cell_nat2w.sh <name> <edge> <cx> <cy> <face> <stem> [orient_blend]
set -uo pipefail
SELF=$(readlink -f "$0")
BASE=/data/group4/20261008-232029-workbuddy-34e89f61/harness_nat2
D="$BASE/rep"; RAW="$BASE/raw"
PY=${S_PY:-/data/group4/20261004-205550-qoder-1280b420/env/bin/python}
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache"
export MUJOCO_GL=disable
unset PYOPENGL_PLATFORM DISPLAY
mkdir -p "$D/tmp" "$D/cache" "$D/out" "$RAW"
ulimit -v 16777216
cd "$D"
NAME=$1; EDGE=$2; CX=$3; CY=$4; FACE=$5; STEM=$6
OB=${7:-0.0}
if [[ -e "$D/out/$NAME" ]]; then printf 'REFUSE %s exists\n' "$NAME" >&2; exit 3; fi
case "$NAME" in *[!a-z0-9_]*) printf 'REFUSE bad name %s\n' "$NAME" >&2; exit 3;; esac
mapfile -t S_FLAGS < "$BASE/.flags_flat"
[ "${#S_FLAGS[@]}" -gt 0 ] || { printf 'REFUSE empty flag list\n' >&2; exit 6; }
EXTRA=("--cube-edge-mm=$EDGE" "--cube-x=$CX" "--cube-y=$CY")
[ "$FACE" != "0" ] && EXTRA+=("--grip-face-half-mm=$FACE")
if [ "$OB" != "0.0" ] && [ "$OB" != "0" ]; then
  EXTRA+=("--approach-orient-servo" "--approach-orient-blend=$OB")
fi
if [ "$STEM" != "-" ]; then export N1_MOTION_STEM="$STEM"; else unset N1_MOTION_STEM || true; fi
META="$RAW/$NAME.meta.txt"
{
  printf 'name=%s\nutc_start=%s\nhost=%s uid=%s\n' "$NAME" "$(date -u +%FT%TZ)" "$(hostname)" "$(id -u)"
  printf 'runner_sha256=%s\nsonic_grasp_sha256=%s\n' "$(sha256sum "$SELF" | cut -d' ' -f1)" "$(sha256sum "$D/sonic_grasp.py" | cut -d' ' -f1)"
  printf 'motion_stem=%s\napproach_orient_blend=%s\n' "${N1_MOTION_STEM:-near_s42}" "$OB"
  printf 'sonic_grasp_args=%s\n' "$NAME ${EXTRA[*]}"
} > "$META" 2>&1
T0=$(date +%s); set +e
timeout --foreground --kill-after=5s 1500 nice -n 19 \
  "$PY" -B sonic_grasp.py "$NAME" "${S_FLAGS[@]}" --branch-coverage "${EXTRA[@]}" > "$RAW/$NAME.stdout.log" 2>&1
RC=$?; set -e; T1=$(date +%s)
{ printf 'utc_end=%s\nrc=%s wall_s=%s\n' "$(date -u +%FT%TZ)" "$RC" "$((T1-T0))";
  printf 'result_json=%s\n' "$D/out/$NAME/result.json"; } >> "$META" 2>&1
if [ -f "$D/out/$NAME/result.json" ]; then cp -a "$D/out/$NAME/result.json" "$RAW/$NAME.result.json"; fi
printf '%s stem=%s ob=%s rc=%s wall=%s\n' "$NAME" "$STEM" "$OB" "$RC" "$((T1-T0))" >> "$BASE/progress.txt"
exit "$RC"
