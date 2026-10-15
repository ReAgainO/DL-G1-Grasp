#!/bin/bash
# WS2: sha256 verify downloaded parquet against LFS-pointer manifest
set -u
BASE="/data/group4/20261008-221515-qoder-03c4673f/ws2_dataset"
RAW="$BASE/raw"
MANIFEST="/tmp/ws2_parquet_manifest.txt"
OUT="$BASE/sha256_verify.txt"
: > "$OUT"
okc=0; badc=0
while read -r ep sha sz; do
  f="$RAW/data/chunk-000/episode_${ep}.parquet"
  if [ ! -s "$f" ]; then echo "MISSING $ep" >> "$OUT"; badc=$((badc+1)); continue; fi
  asz=$(stat -c%s "$f")
  asha=$(sha256sum "$f" | cut -d' ' -f1)
  if [ "$asha" = "$sha" ] && [ "$asz" = "$sz" ]; then
    okc=$((okc+1))
  else
    echo "MISMATCH $ep actual_size=$asz expect_size=$sz actual_sha=$asha expect_sha=$sha" >> "$OUT"
    badc=$((badc+1))
  fi
done < "$MANIFEST"
echo "VERIFY_OK=$okc VERIFY_BAD=$badc" >> "$OUT"
echo "sha256 verify: ok=$okc bad=$badc"
tail -3 "$OUT"
