#!/usr/bin/env bash
# Regenerate the Kimodo motions at the proven 100-step setting.
# The 20-step run produced degenerate clips: the right shoulder pitched through
# 4.7 rad and the root translated +-1.6 m, which is not a "reach to a cube".
# Four job/seed pairs are run in parallel (8 threads each on a 128-core box).
set -uo pipefail
D=/data/group4/20261008-232029-workbuddy-34e89f61
K=/home/group4/group4_dasc7606c/repos/kimodo
PY=/data/group4/20261005-004258-qoder-3be23f19/env-kimodo/bin/python
OUT="$D/kimodo100"; LOG="$D/kimodo_logs"
mkdir -p "$OUT" "$LOG" "$D/tmp" "$D/cache"

export PYTHONPATH="$K"
export HF_HOME=/home/group4/group4_dasc7606c/weights/hf_offline_cache
export HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MUSA_VISIBLE_DEVICES= CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache"

launch () {                    # stem seed prompt
  local stem="$1" seed="$2" prompt="$3"
  local box="$D/kimodo100_input_$stem"
  mkdir -p "$box"
  printf '{"text": "%s", "duration": 4.0}\n' "$prompt" > "$box/meta.json"
  ( cd "$K" && exec nice -n 19 "$PY" -B kimodo/scripts/generate.py \
      --input_folder "$box" --model kimodo-g1-rp \
      --output "$OUT/$stem" \
      --num_samples 1 --diffusion_steps 100 \
      --cfg_type separated --cfg_weight 2.0 2.0 --seed "$seed" ) \
    > "$LOG/$stem.100.log" 2>&1 &
  echo "  launched $stem (seed $seed) pid=$!"
}

launch reach_s43 43 "A person reaches forward with their right hand to grab a small object on a table."
launch reach_s7   7 "A person reaches forward with their right hand to grab a small object on a table."
launch lift_s42  42 "A standing person slowly lifts a small object upward with their right hand and keeps the left arm relaxed."
launch lift_s7    7 "A standing person slowly lifts a small object upward with their right hand and keeps the left arm relaxed."
wait
echo "--- results ---"
ls -la "$OUT"
echo ALL_DONE
