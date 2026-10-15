#!/usr/bin/env bash
# Lane A2 independent replication runner.
#
# Deliberate differences from the owner's run.sh (which lane A2 must NOT call):
#   * NO reserve_cpu_trial.py quota gate   (owner private budget)
#   * NO rules_sha / AGENTS.md assertion   (owner launch contract)
#   * NO snapshot_sources.py               (owner snapshot writer)
#   * NO tee into /home/.../logs/<owner task>/steps.md
#   * timeout 900 s instead of 300 s
# Everything else (env exports, AS ulimit, taskset, cd-to-copy-root) mirrors it,
# because those are physically load-bearing for the replication.
#
# Usage:  bash run_own.sh <OUTPUT_NAME> [sonic_grasp.py options...]
# Env:    A2_CPUS="a,b,c,d"  (default: first 4 CPUs of this process affinity)
#         A2_TIMEOUT=900     A2_NICE=19
set -euo pipefail

T=20261008-023143-qoder-d266d3a9
D=/data/group4/$T/A2_sonicrep
PY=${STAGE_PY:-/data/group4/20261004-205550-qoder-1280b420/env/bin/python}

export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache"
export MUJOCO_GL=disable
unset PYOPENGL_PLATFORM
unset DISPLAY

mkdir -p "$D/tmp" "$D/cache" "$D/out" "$D/raw"
ulimit -v 16777216

# sonic_grasp.py resolves everything from Path(__file__).parent, but keep the
# owner's cd-to-project-root discipline anyway.
cd "$D"

NAME=${1:?need an OUTPUT_NAME (must be a fresh, unused name)}
shift

if [[ -e "$D/out/$NAME" ]]; then
  printf 'REFUSE: %s/out/%s already exists; pick a fresh name\n' "$D" "$NAME" >&2
  exit 3
fi

CPUS=${A2_CPUS:-$(/usr/bin/python3 -B -c 'import os;print(",".join(map(str,sorted(os.sched_getaffinity(0))[:4])))')}
TMO=${A2_TIMEOUT:-900}
NICE=${A2_NICE:-19}

LOG="$D/raw/$NAME.stdout.log"
META="$D/raw/$NAME.meta.txt"

RUNNER_SHA=$(sha256sum "$0" | cut -d' ' -f1)
GRASP_SHA=$(sha256sum "$D/sonic_grasp.py" | cut -d' ' -f1)
VERS=$("$PY" -B -c "import sys;sys.path.insert(0,'$D/pydeps');import mujoco,numpy,onnxruntime;print('mujoco',mujoco.__version__,'numpy',numpy.__version__,'ort',onnxruntime.__version__,'py',sys.version.split()[0])")

{
  printf 'name=%s\n' "$NAME"
  printf 'utc_start=%s\n' "$(date -u +%FT%TZ)"
  printf 'host=%s uid=%s\n' "$(hostname)" "$(id -u)"
  printf 'runner_sha256=%s\n' "$RUNNER_SHA"
  printf 'sonic_grasp_sha256=%s\n' "$GRASP_SHA"
  printf 'py=%s\n' "$PY"
  printf 'versions=%s\n' "$VERS"
  printf 'cpus=%s timeout=%ss nice=%s ulimit_v_KiB=%s\n' "$CPUS" "$TMO" "$NICE" "$(ulimit -v)"
  printf 'sonic_grasp_args=%s %s\n' "$NAME" "$*"
  printf 'pressure_cpu: '; tr '\n' ' ' < /proc/pressure/cpu; printf '\n'
  printf 'pressure_memory: '; tr '\n' ' ' < /proc/pressure/memory; printf '\n'
  printf 'df_home_data:\n'; df -h /home /data | sed 's/^/  /'
} > "$META" 2>&1

T0=$(date +%s)
set +e
timeout --foreground --kill-after=5s "$TMO" \
  taskset -c "$CPUS" nice -n "$NICE" \
  "$PY" -B sonic_grasp.py "$NAME" "$@" > "$LOG" 2>&1
RC=$?
set -e
T1=$(date +%s)

{
  printf 'utc_end=%s\n' "$(date -u +%FT%TZ)"
  printf 'rc=%s wall_s=%s\n' "$RC" "$((T1 - T0))"
  printf 'result_json=%s\n' "$D/out/$NAME/result.json"
  printf 'pressure_cpu_after: '; tr '\n' ' ' < /proc/pressure/cpu; printf '\n'
} >> "$META" 2>&1

if [[ -f "$D/out/$NAME/result.json" ]]; then
  cp -a "$D/out/$NAME/result.json" "$D/raw/$NAME.result.json"
fi

printf 'A2RUN name=%s rc=%s wall_s=%s log=%s\n' "$NAME" "$RC" "$((T1 - T0))" "$LOG"
exit "$RC"
