#!/usr/bin/env bash
# W4e setup: copy rep_base -> rep_ext_comb (our own copy), point all hardcoded
# BASE paths at it, and rebuild the raw/ + rep/out layout the same way the two
# reference arms did. rep_base is the read-only source; nothing else is touched.
set -euo pipefail
M=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate
SRC=$M/rep_base
DST=$M/rep_ext_comb
[ -e "$DST" ] && { echo "REFUSE $DST exists"; exit 3; }
cp -a "$SRC" "$DST"
cd "$DST"
sed -i "s#^BASE=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base\$#BASE=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_comb#" run_fixE.sh
sed -i "s#^BASE = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base')#BASE = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_comb')#" fixE_tally.py
for f in drive_phase1.sh drive_phase2.sh drive_phase3.sh run_my.sh; do
  sed -i "s#/ws4_migrate/rep_base#/ws4_migrate/rep_ext_comb#g" "$f"
done
echo "== leftover rep_base references (expect none) =="
grep -n "rep_base" run_fixE.sh fixE_tally.py drive_phase1.sh drive_phase2.sh drive_phase3.sh run_my.sh || echo "(none)"
echo "== new BASE lines =="
grep -n "rep_ext_comb" run_fixE.sh fixE_tally.py drive_phase1.sh drive_phase2.sh drive_phase3.sh run_my.sh
mv raw raw_src_snapshot
mkdir -p raw
mv rep/out rep/out_ws4a_baseline_keep
mkdir -p rep/out
cp -a rep/out_ws4a_baseline_keep/generated_phases2 rep/out/generated_phases2
cp -a rep/out_ws4a_baseline_keep/official-dynamics.json rep/out_ws4a_baseline_keep/pinch-feasibility.json rep/out/
echo "== rep/out rebuilt =="
ls rep/out/
ls rep/out/generated_phases2 | head -6
echo "== gates: .flags_flat vs rep_base =="
cmp -s "$DST/.flags_flat" "$SRC/.flags_flat" && echo "flags_flat byte-identical" || echo "FLAGS DIFF!"
sha256sum "$DST/.flags_flat" "$SRC/.flags_flat"
du -sh "$DST"
