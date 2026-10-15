#!/usr/bin/env bash
# Generate the two Kimodo motions this task needs:
#   reach_s43  - right arm reaches forward to the object on the table
#   lift_s42   - right arm lifts the object upward
# Mirrors the prompt/seed pair the official S1000 lane used for its ARDY clips,
# so Kimodo and ARDY can be compared on identical wording.
# Outputs <D>/kimodo/<stem>.npz + .csv  (Kimodo native 30 fps, G1Skeleton34).
set -uo pipefail
D=/data/group4/20261008-232029-workbuddy-34e89f61
K=/home/group4/group4_dasc7606c/repos/kimodo
PY=/data/group4/20261005-004258-qoder-3be23f19/env-kimodo/bin/python
OUT="$D/kimodo"; IN="$D/kimodo_input"; LOG="$D/kimodo_logs"
mkdir -p "$OUT" "$IN" "$LOG"

export PYTHONPATH="$K"
export HF_HOME=/home/group4/group4_dasc7606c/weights/hf_offline_cache
export HF_HUB_OFFLINE=1
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MUSA_VISIBLE_DEVICES= CUDA_VISIBLE_DEVICES=
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$D/tmp" XDG_CACHE_HOME="$D/cache"
mkdir -p "$D/tmp" "$D/cache"
# AGENTS.md 16: never let a sampling loop eat the shared 1 TB box.
ulimit -v $((40 * 1024 * 1024))

gen () {                       # stem  seed  prompt
  local stem="$1" seed="$2" prompt="$3"
  local box="$D/kimodo_input_$stem"
  mkdir -p "$box"
  printf '{"text": "%s", "duration": 4.0}\n' "$prompt" > "$box/meta.json"
  echo "=== $stem seed=$seed ==="
  ( cd "$K" && exec nice -n 19 "$PY" -B kimodo/scripts/generate.py \
      --input_folder "$box" --model kimodo-g1-rp \
      --output "$OUT/$stem" \
      --num_samples 1 --diffusion_steps 20 \
      --cfg_type separated --cfg_weight 2.0 2.0 --seed "$seed" ) \
    > "$LOG/$stem.log" 2>&1
  local rc=$?
  echo "  rc=$rc"
  ls -la "$OUT/$stem.npz" "$OUT/$stem.csv" 2>&1 | sed 's/^/  /'
  tail -2 "$LOG/$stem.log" | tr '\r' '\n' | sed 's/^/  /'
}

gen reach_s43 43 "A person reaches forward with their right hand to grab a small object on a table."
gen lift_s42  42 "A standing person slowly lifts a small object upward with their right hand and keeps the left arm relaxed."
echo ALL_DONE
