#!/bin/bash
# ws4 step 04b: verify copy fidelity + prepare runnable copy (BASE repoint, fresh raw/out)
set -uo pipefail
SRC=/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base
V=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/verify
mkdir -p "$V"
echo "== [1] sha256 tree diff (src vs copy, excluding historical out dirs) =="
( cd "$SRC" && find . -path ./rep/out -prune -o -path ./rep/out_b1_keep -prune -o \
    -path ./rep/out_broken_phase1 -prune -o -path ./rep/cache -prune -o \
    -name __pycache__ -prune -o -type f -print0 \
  | xargs -0 sha256sum | sort -k2 ) > "$V/src.sha256"
( cd "$DST" && find . -type f -print0 | xargs -0 sha256sum | sort -k2 ) > "$V/dst.sha256"
echo "src_lines=$(wc -l < "$V/src.sha256") dst_lines=$(wc -l < "$V/dst.sha256")"
if diff -q "$V/src.sha256" "$V/dst.sha256" >/dev/null; then
  echo "SHA256_TREE_IDENTICAL: all $(wc -l < "$V/dst.sha256") files match source"
else
  echo "SHA256_DIFFS:"; diff "$V/src.sha256" "$V/dst.sha256" | head -20
fi
echo
echo "== [2] key file shas in copy (must equal source values) =="
cd "$DST/rep" && sha256sum sonic_grasp.py native_branch.py adaptive_hand.py grasp_geometry.py \
  reference_filter.py src/original_motions/new_motion_cube_a_s42.npz src/manual_grasp_calibration.npz
echo "-- .flags_flat sha (copy vs src) --"
sha256sum "$DST/.flags_flat" "$SRC/.flags_flat" | awk '{print $1, $2}'
echo
echo "== [3] repoint BASE in copy's run_fixE.sh (source file untouched) =="
cp -a "$DST/run_fixE.sh" "$DST/run_fixE.sh.orig_from_source"
sed -i "s#^BASE=/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE\$#BASE=$DST#" "$DST/run_fixE.sh"
grep -n '^BASE=' "$DST/run_fixE.sh"
echo "src run_fixE.sh sha (must be unchanged):"; sha256sum "$SRC/run_fixE.sh"
echo
echo "== [4] isolate source evidence, create fresh raw/ and out/ =="
mv "$DST/raw" "$DST/raw_src_snapshot"
mkdir -p "$DST/raw" "$DST/rep/out" "$DST/rep/tmp" "$DST/rep/cache"
echo "raw_src_snapshot meta files: $(ls "$DST/raw_src_snapshot" | wc -l)"
ls -la "$DST" | head -30
echo
echo "== [5] hardcoded source-path scan in python sources (safety: must not write to source) =="
echo "-- occurrences of the source task id in .py --"
grep -rl '20261008-182000-qoder-7d11d1ae' "$DST/rep" --include='*.py' 2>/dev/null | head -10
echo "-- occurrences in .sh --"
grep -rn '20261008-182000-qoder-7d11d1ae' "$DST"/*.sh 2>/dev/null | head -10
echo "(scan done)"
