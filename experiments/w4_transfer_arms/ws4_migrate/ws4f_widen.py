# W4f: minimal input-domain widening in the derived copy rep_ext_comb80.
# Widen ONLY the two input-domain guards that block cube_edge=80mm from being
# expressed at all (scene edge domain, live cube-half domain). No success gate,
# no physics recipe, no flags file, and no grip-geometry threshold is touched.
import difflib, hashlib, sys, pathlib

M = pathlib.Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
SRC = M / 'rep_ext_comb'
DST = M / 'rep_ext_comb80'
LOG = M / 'logs'

EDITS = [
    ('rep/sonic_grasp.py',
     "not 10.<=cube_edge_mm<=50.:raise ValueError('Cube edge must be finite and 10..50mm')",
     "not 10.<=cube_edge_mm<=80.:raise ValueError('Cube edge must be finite and 10..80mm (W4f widened input domain; success gates untouched)')"),
    ('rep/sonic_grasp.py',
     "and 10<=a.cube_edge_mm<=50,'A3: cube edge domain is 10..50mm'",
     "and 10<=a.cube_edge_mm<=80,'A3: cube edge domain is 10..80mm (W4f widened input domain for the 80mm-cube test)'"),
    ('rep/adaptive_hand.py',
     "not .004<=self.cube_half_m<=.030:raise ValueError('cube half-extent must be finite and 4..30mm')",
     "not .004<=self.cube_half_m<=.045:raise ValueError('cube half-extent must be finite and 4..45mm (W4f widened input domain)')"),
    ('rep/grasp_geometry.py',
     "not .004<=half<=.030:raise ValueError('Cube half-extent must be finite and 4..30mm')",
     "not .004<=half<=.045:raise ValueError('Cube half-extent must be finite and 4..45mm (W4f widened input domain)')"),
]

out = []
for rel, old, new in EDITS:
    p = DST / rel
    t = p.read_text()
    n = t.count(old)
    if n != 1:
        print('FAIL count=%d for %s :: %s' % (n, rel, old), file=sys.stderr)
        sys.exit(2)
    p.write_text(t.replace(old, new, 1))
    out.append('EDIT ok %s :: %s' % (rel, new[:80]))

# syntax check in memory (no .pyc written)
for rel in ['rep/sonic_grasp.py', 'rep/adaptive_hand.py', 'rep/grasp_geometry.py']:
    compile((DST / rel).read_text(), str(DST / rel), 'exec')
    out.append('syntax OK %s' % rel)

diff_lines = []
for rel in ['rep/sonic_grasp.py', 'rep/adaptive_hand.py', 'rep/grasp_geometry.py',
            'rep/finger_control.py', 'run_fixE.sh', '.flags_flat']:
    a = (SRC / rel).read_bytes()
    b = (DST / rel).read_bytes()
    if a == b:
        out.append('BITWISE-SAME %s' % rel)
    else:
        d = difflib.unified_diff(a.decode().splitlines(), b.decode().splitlines(),
                                 fromfile='comb/' + rel, tofile='comb80/' + rel, lineterm='')
        diff_lines.append('\n'.join(d))
        out.append('DIFFERS %s' % rel)
for rel in ['rep/sonic_grasp.py', 'rep/adaptive_hand.py', 'rep/grasp_geometry.py',
            'rep/finger_control.py', 'run_fixE.sh', '.flags_flat']:
    out.append('sha256 comb80 %s %s' % (hashlib.sha256((DST / rel).read_bytes()).hexdigest(), rel))
    out.append('sha256 comb   %s %s' % (hashlib.sha256((SRC / rel).read_bytes()).hexdigest(), rel))

LOG.mkdir(exist_ok=True)
(LOG / 'ws4f_widen.diff').write_text('\n\n'.join(diff_lines) + '\n')
print('\n'.join(out))
