#!/bin/bash
# WS2: download 118 parquet + meta from ModelScope (no videos)
set -u
BASE="/data/group4/20261008-221515-qoder-03c4673f/ws2_dataset"
RAW="$BASE/raw"
URL="https://www.modelscope.cn/api/v1/datasets/mncai/G1_Dex3_Trash_LocoManipulation/repo"
LOG="$BASE/download.log"
mkdir -p "$RAW/data/chunk-000" "$RAW/meta"
echo "=== START $(date '+%F %T') ===" >> "$LOG"

ok=0; fail=0
for i in $(seq 0 117); do
  ep=$(printf "%06d" $i)
  f="$RAW/data/chunk-000/episode_${ep}.parquet"
  if [ -s "$f" ] && [ "$(stat -c%s "$f")" -gt 1000 ]; then
    echo "SKIP episode_${ep} (exists size=$(stat -c%s "$f"))" >> "$LOG"; ok=$((ok+1)); continue
  fi
  meta=$(curl -sL --retry 2 --retry-delay 2 -w "%{http_code} %{size_download} %{time_total}" -o "$f.tmp" "$URL?Revision=master&FilePath=data/chunk-000/episode_${ep}.parquet")
  sz=$(stat -c%s "$f.tmp" 2>/dev/null || echo 0)
  if [ "$sz" -gt 1000 ]; then mv "$f.tmp" "$f"; ok=$((ok+1)); else rm -f "$f.tmp"; fail=$((fail+1)); fi
  echo "DL episode_${ep}.parquet http_size_time=[$meta] actual_size=$sz" >> "$LOG"
done
for m in info.json episodes.jsonl tasks.jsonl modality.json; do
  f="$RAW/meta/$m"
  meta=$(curl -sL --retry 2 --retry-delay 2 -w "%{http_code} %{size_download}" -o "$f.tmp" "$URL?Revision=master&FilePath=meta/$m")
  sz=$(stat -c%s "$f.tmp" 2>/dev/null || echo 0)
  if [ "$sz" -gt 10 ]; then mv "$f.tmp" "$f"; else rm -f "$f.tmp"; fi
  echo "DL meta/$m http_size=[$meta] actual_size=$sz" >> "$LOG"
done
echo "=== DONE $(date '+%F %T') ok=$ok fail=$fail ===" >> "$LOG"
