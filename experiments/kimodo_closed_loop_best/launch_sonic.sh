#!/usr/bin/env bash
# Launch scene-conditioned Kimodo generations, fully detached (setsid) so they
# survive the SSH channel closing.  Poll the per-seed logs afterwards.
set -u
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

PROMPT="A standing person reaches forward with their right hand, grasps a small cube resting on a table in front of them, and lifts it upward."

for seed in 42 43 7; do
  stem="sonic_c$seed"
  setsid nohup nice -n 19 "$PY" -u -B "$K/kimodo/scripts/generate.py" \
      "$PROMPT" \
      --constraints "$W/sonic_constraints.json" --duration 5.0 \
      --model kimodo-g1-rp --output "$OUT/$stem" \
      --num_samples 1 --diffusion_steps 100 --seed "$seed" \
      > "$LOG/$stem.log" 2>&1 < /dev/null &
  echo "  detached $stem pid=$!"
done
sleep 3
ps -ef | grep -c "[g]enerate.py"
