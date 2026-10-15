#!/bin/bash
# ws4 step 06: patch tally BASE in own copy, run tally on own copy, compare row to source row
set -uo pipefail
SRC=/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base
PY=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
L=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/logs
echo "== [1] protect + repoint fixE_tally.py in own copy (it WRITES fixE_tally.csv into BASE) =="
cp -a "$DST/fixE_tally.csv" "$DST/fixE_tally_src_snapshot.csv"
cp -a "$DST/fixE_tally.py" "$DST/fixE_tally.py.orig_from_source"
sed -i "s#^BASE = Path('/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE')#BASE = Path('$DST')#" "$DST/fixE_tally.py"
grep -n "^BASE\|^CUT" "$DST/fixE_tally.py"
echo "src fixE_tally.py sha (must be unchanged): $(sha256sum $SRC/fixE_tally.py | cut -d' ' -f1)"
echo "src fixE_tally.csv sha (must be unchanged): $(sha256sum $SRC/fixE_tally.csv | cut -d' ' -f1)"
echo
echo "== [2] run patched tally under my copy (CUT=0 -> all results in MY out/) =="
cd "$DST" && PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 "$PY" fixE_tally.py 0 2>&1 | tee "$L/tally_mine.txt"
echo
echo "== [3] my tally CSV ==="
cat "$DST/fixE_tally.csv"
echo
echo "== [4] side-by-side with the SOURCE row for e35n_00_06 =="
echo "source CSV header + anchor row:"
head -1 "$SRC/fixE_tally.csv"
grep '^e35n_00_06,' "$SRC/fixE_tally.csv"
echo "mine CSV header + anchor row:"
head -1 "$DST/fixE_tally.csv"
grep '^e35n_00_06,' "$DST/fixE_tally.csv"
echo
echo "== [5] byte-compare the two anchor rows =="
A=$(grep '^e35n_00_06,' "$SRC/fixE_tally.csv")
B=$(grep '^e35n_00_06,' "$DST/fixE_tally.csv")
if [ "$A" = "$B" ]; then echo "ROW_IDENTICAL: $A"; else echo "ROW_DIFF"; echo " src=$A"; echo " mine=$B"; fi
echo
echo "== [6] own progress.txt tail (written by run_fixE.sh in MY copy) =="
tail -3 "$DST/progress.txt"
