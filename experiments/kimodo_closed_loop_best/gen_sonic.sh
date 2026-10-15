#!/usr/bin/env bash
# Sanctioned scene-conditioned Kimodo generation.
# Runs the SONIC team's own wrapper (work/sonic_generate/generate_sonic.py),
# which pins --constraints sonic_constraints.json (right hand waypoints on the
# cube, in Kimodo's Y-up frame) and --duration 5.0.
set -uo pipefail
D=/data/group4/20261008-232029-workbuddy-34e89f61
K=/home/group4/group4_dasc7606c/repos/kimodo
W=/home/group4/group4_dasc7606c/work/sonic_generate
PY=/data/group4/20261005-004258-qoder-3be23f19/env-kimodo/bin/python
OUT="$D/kimodo_sonic"; LOG="$D/kimodo_logs"
mkdir -p "$OUT" "$LOG" "$D/tmp" "$D/cache"

export PYTHONPATH="$K"
export HF_HOME=/home/group4/group4_dasc7606c/weights/hf_offline_cache
export HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MUSA_VISIBLE_DEVICES= CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache"
ulimit -v $((40 * 1024 * 1024))

PROMPT="A standing person reaches forward with their right hand, grasps a small cube resting on a table in front of them, and lifts it upward."

go () {                       # seed
  local seed="$1"
  local stem="sonic_c$seed"
  ( cd "$K" && exec nice -n 19 "$PY" -B "$W/generate_sonic.py" \
      "$PROMPT" \
      --model kimodo-g1-rp --output "$OUT/$stem" \
      --num_samples 1 --diffusion_steps 100 --seed "$seed" ) \
    > "$LOG/$stem.log" 2>&1 &
  echo "  launched $stem seed=$seed pid=$!"
}

go 42
go 43
go 7
wait
echo "--- results ---"
ls -la "$OUT"
echo SONIC_GEN_DONE
