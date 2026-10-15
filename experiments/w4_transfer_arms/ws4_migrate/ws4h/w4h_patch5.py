#!/usr/bin/env python3
"""W4h patch 5: make the temporary cube fixture RIGID via solimp (rep_ext_w1 only).
Measured: the default equality solimp [0.9,0.95,0.001] gives an effective weld stiffness of
~83 N/m (2N -> 24mm sag; solref is irrelevant), destroying the preset seat. solimp
[0.9999,0.99999,1e-5] gives 0.033mm sag at 2N. Marked W4h variant; the weld is released at
LIFT (or CLOSE) as before."""
from pathlib import Path
import hashlib
SG = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_w1/rep/sonic_grasp.py')
src = SG.read_text()
old = "ET.SubElement(equality,'weld',name='w4h_cube_fixture',body1='red_cube',solref='.0002 1')"
assert src.count(old) == 1, 'anchor'
src = src.replace(old, "ET.SubElement(equality,'weld',name='w4h_cube_fixture',body1='red_cube',solref='.002 1',solimp='0.9999 0.99999 0.00001') # W4h W1S: rigid fixture (solimp, measured 0.03mm/2N; default solimp = 83 N/m soft)")
SG.write_text(src)
print('weld solimp rigid OK sha256=%s' % hashlib.sha256(src.encode()).hexdigest())
