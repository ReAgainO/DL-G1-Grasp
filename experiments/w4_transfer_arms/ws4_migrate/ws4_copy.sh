#!/bin/bash
# ws4 step 04: copy rep_fixE to own sandbox (source strictly read-only)
set -uo pipefail
SRC=/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base
echo "== [1] source pre-state (read-only evidence) =="
stat -c '%y %s %n' "$SRC/fixE_tally.csv" "$SRC/run_fixE.sh" "$SRC/.flags_flat"
echo
echo "== [2] tar copy, excluding historical out dirs + __pycache__ =="
mkdir -p "$DST" || exit 2
cd "$SRC" || exit 2
time tar --exclude='./rep/out' --exclude='./rep/out_b1_keep' --exclude='./rep/out_broken_phase1' \
     --exclude='./rep/cache' --exclude='__pycache__' -cf - . | (cd "$DST" && tar -xf -)
echo "tar_rc=$?"
echo
echo "== [3] copy size =="
du -sh "$DST"
du -sh "$DST"/* 2>/dev/null | sort -h | tail -8
echo "-- rep/ inside copy --"
du -sh "$DST"/rep/* 2>/dev/null | sort -h | tail -10
echo
echo "== [4] file counts (src vs dst, excluding out dirs) =="
s=$(cd "$SRC" && find . -path ./rep/out -prune -o -path ./rep/out_b1_keep -prune -o -path ./rep/out_broken_phase1 -prune -o -path ./rep/cache -prune -o -name __pycache__ -prune -o -type f -print | wc -l)
d=$(cd "$DST" && find . -type f | wc -l)
echo "src_files=$s dst_files=$d"
