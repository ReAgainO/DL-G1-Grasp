#!/usr/bin/env bash
# Scene-conditioned Kimodo generation, calling generate.py directly with the
# SONIC constraint file (identical to what work/sonic_generate/generate_sonic.py
# wraps, but with unbuffered output so progress is observable).
#
# Constraint (sonic_constraints.json, sha dba75a18...): right-hand waypoints
#   frame  45 (1.5 s)  hand at (-0.118, 0.9245, 0.267)  = 15 cm above the cube
#   frame  75 (2.5 s)  hand at (-0.118, 0.7745, 0.267)  = at the cube
#   frame 105 (3.5 s)  hand at (-0.118, 0.7745, 0.267)  = hold at the cube
#   frame 135 (4.5 s)  hand at (-0.118, 1.0245, 0.267)  = lifted 25 cm
# in Kimodo's Y-up frame, i.e. scene (y, z, x) of cube [0.267, -0.118, 0.7745].
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

PROMPT="A standing person reaches forward with their right hand, grasps a small cube resting on a table in front of them, and lifts it upward."

go () {                       # seed
  local seed="$1" stem="sonic_c$1"
  ( cd "$K" && exec nice -n 19 "$PY" -u -B kimodo/scripts/generate.py \
      "$PROMPT" \
      --constraints "$W/sonic_constraints.json" --duration 5.0 \
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
echo SONIC_GEN2_DONE
