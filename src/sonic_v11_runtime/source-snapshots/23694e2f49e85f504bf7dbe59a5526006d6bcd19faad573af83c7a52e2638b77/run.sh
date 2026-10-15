#!/usr/bin/env bash
set -euo pipefail
T=20261006-093203-codex-6385a841
B=/home/group4/group4_dasc7606c
D=/data/group4/$T
PY=${STAGE_PY:-/data/group4/20261004-205550-qoder-1280b420/env/bin/python}
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache"
export MUJOCO_GL=disable
unset PYOPENGL_PLATFORM
if [[ ${ARDY_RENDER:-0} == 1 ]]; then
  export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa LP_NUM_THREADS=1
  export LD_LIBRARY_PATH="$B/render_test/mesa_probe/x_libosmesa6_23.2.1-1ubuntu3.1~22.04.4_amd64/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
unset DISPLAY
if [[ ${ARDY_GENERATE:-0} == 1 ]]; then
  ulimit -v 41943040
else
  ulimit -v 16777216
fi
cd "$D"
RULES_SHA=$(sha256sum "$B/AGENTS.md")
[[ ${RULES_SHA%% *} == 68db8493e678a0cab6613610a8d87f4fca6597f8369ccd5a75cea089bfd41db6 ]] || { printf 'STOP: collaboration rules changed; read the new rules first\n' >&2; exit 9; }
CPUS=$(python3 -B -c 'import os;print(",".join(map(str,sorted(os.sched_getaffinity(0))[:4])))')
LOG="$B/logs/$T/run-$(date +%Y%m%d-%H%M%S-%N).log"
printf '\n## [run] %s bounded CPU stage\n- command: %q ' "$(date -Is)" "$PY" >> "$B/logs/$T/steps.md"
printf '%q ' "$@" >> "$B/logs/$T/steps.md"
printf '\n- bound: 4 CPUs=%s, AS_KiB=%s, timeout300s; stdout=%s\n' "$CPUS" "$(ulimit -v)" "$LOG" >> "$B/logs/$T/steps.md"
df -h /home/group4 /data/group4 /tmp >> "$LOG"
cat /proc/pressure/memory >> "$LOG"
cat /proc/pressure/cpu >> "$LOG"
free -h >> "$LOG"
python3 -B "$D/snapshot_sources.py" >> "$LOG"
set +e
if [[ ${1##*/} == sonic_grasp.py ]]; then
  python3 -B "$D/reserve_cpu_trial.py" "$1" "$2" 2>&1 | tee -a "$LOG"
  GUARD_RC=${PIPESTATUS[0]}
  if [[ $GUARD_RC != 0 ]]; then
    printf '\n- launch_guard_exit=%s; physics NOT launched\n' "$GUARD_RC" >> "$B/logs/$T/steps.md"
    exit "$GUARD_RC"
  fi
fi
timeout --foreground --kill-after=5s 300 taskset -c "$CPUS" "$PY" -B "$@" 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
set -e
df -h /home/group4 /data/group4 /tmp >> "$LOG"
cat /proc/pressure/memory >> "$LOG"
cat /proc/pressure/cpu >> "$LOG"
free -h >> "$LOG"
printf '\n- exit=%s\n' "$RC" >> "$B/logs/$T/steps.md"
exit "$RC"
