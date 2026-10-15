#!/bin/bash
# Sequential weight downloader for Kimodo / LLM2Vec / ARDY via hf-mirror
R=/home/group4/group4_dasc7606c
export HF_ENDPOINT=https://hf-mirror.com
B=$R/envs/weights/.venv/bin
LOG=$R/logs/weights/dl_all.log
SUM=$R/logs/weights/summary.tsv
REPOS="nvidia/Kimodo-G1-RP-v1 weights/kimodo
nvidia/Kimodo-G1-SEED-v1 weights/kimodo
nvidia/Kimodo-SOMA-RP-v1.1 weights/kimodo
nvidia/Kimodo-SOMA-SEED-v1.1 weights/kimodo
nvidia/Kimodo-SOMA-RP-v1 weights/kimodo
nvidia/Kimodo-SMPLX-RP-v1 weights/kimodo
nvidia/Kimodo-SOMA-SEED-v1 weights/kimodo
nvidia/TMR-SOMA-RP-v1 weights/kimodo
McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp weights/ardy_textenc
McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp-supervised weights/ardy_textenc
nvidia/ARDY-G1-RP-25FPS-Horizon52 weights/ardy_ckpt
nvidia/ARDY-G1-RP-25FPS-Horizon8 weights/ardy_ckpt
nvidia/ARDY-Core-RP-20FPS-Horizon40 weights/ardy_ckpt
nvidia/ARDY-Core-RP-20FPS-Horizon8 weights/ardy_ckpt"

echo "$REPOS" | while read -r repo dir; do
  [ -z "$repo" ] && continue
  avail_gb=$(df --output=avail -BG /home | tail -1 | tr -dc "0-9")
  if [ "$avail_gb" -lt 30 ]; then
    echo "ABORT_DISK availsys=$avail_gb before $repo" | tee -a "$LOG" >> "$SUM"
    break
  fi
  name=${repo#*/}
  dest=$R/$dir/$name
  echo "START $(date +%FT%T) repo=$repo dest=$dest avail=${avail_gb}G" | tee -a "$LOG"
  start=$(date +%s)
  "$B/hf" download "$repo" --local-dir "$dest" >> "$LOG" 2>&1
  rc=$?
  end=$(date +%s); el=$((end-start))
  bytes=$(find "$dest" -type f -not -path "*/.cache/*" -printf "%s\n" 2>/dev/null | awk '{s+=$1} END {print s+0}')
  rate=$(awk -v b="$bytes" -v t="$el" 'BEGIN{if(t>0) printf "%.1f", b/1048576/t; else printf "0"}')
  echo "RESULT $(date +%FT%T) repo=$repo rc=$rc elapsed=${el}s bytes=$bytes rate_MBps=$rate dest=$dest" | tee -a "$LOG"
  printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$repo" "$rc" "$el" "$bytes" "$rate" "$dest" >> "$SUM"
done
echo "ALLDONE $(date +%FT%T)" | tee -a "$LOG"
