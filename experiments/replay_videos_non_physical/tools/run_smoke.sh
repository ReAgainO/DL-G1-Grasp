#!/usr/bin/env bash
# q2_smoke wrapper: identical env to run_video.sh, but runs the pre-flight checker.
set -euo pipefail
T=/data/group4/20261009-132809-qoder-9b946d7f
B=/home/group4/group4_dasc7606c
export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa
export LD_LIBRARY_PATH="$B/render_test/mesa_probe/x_libosmesa6_23.2.1-1ubuntu3.1~22.04.4_amd64/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
unset MUSA_VISIBLE_DEVICES MTHREADS_VISIBLE_DEVICES DISPLAY
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
ulimit -v 16777216
PY=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
CPUS=${CPUS:-56,57}
exec nice -n 19 taskset -c "$CPUS" "$PY" -B "$T/tools/q2_smoke.py" "$@"
