#!/usr/bin/env bash
# Re-apply the NAT-EXP patch correctly (previous attempt dropped a leading space).
set -euo pipefail
F=/data/group4/20261008-232029-workbuddy-34e89f61/harness_nat/rep/sonic_grasp.py
ORIG=$(ls "$F".orig-* 2>/dev/null | head -1)
[ -n "$ORIG" ] || { echo "no .orig backup"; exit 3; }
cp -a "$ORIG" "$F"
echo "restored from $ORIG"

python3 - "$F" <<'PY'
import sys
p = sys.argv[1]
src = open(p).read()

old_sig = "branch_coverage=False):"
assert src.count(old_sig) == 1
src = src.replace(old_sig, "branch_coverage=False,flat_pinch_relax=1.):")

old = "    J=np.vstack([J,10*(jp[2,av]-jp2[2,av]),10*(jp3[2,av]-jp2[2,av])]);err=np.r_[err,-10*heights];er=heights"
assert src.count(old) == 1
new = "    J=np.vstack([J,10*flat_pinch_relax*(jp[2,av]-jp2[2,av]),10*flat_pinch_relax*(jp3[2,av]-jp2[2,av])]);err=np.r_[err,-10*flat_pinch_relax*heights];er=heights"
src = src.replace(old, new)

anchor = "\na=p.parse_args()"
assert src.count(anchor) == 1, src.count(anchor)
# keep the same one-leading-space style the other p.add_argument lines use
flag = "\n p.add_argument('--flat-pinch-relax',type=float,default=1.,help='NAT-EXP: scale fingertip coplanarity demand in flat_pinch (1=original)')"
src = src.replace(anchor, flag + anchor, 1)

open(p, "w").write(src)
print("patched")
PY

echo "after sha=$(sha256sum "$F" | cut -d' ' -f1)"
/usr/bin/python3 -c "import ast; ast.parse(open('$F').read()); print('AST OK')"
echo "--- around insert ---"
grep -n -- "--flat-pinch-relax" "$F"
grep -n "^a=p.parse_args()" "$F"
echo PATCH_NAT_OK
