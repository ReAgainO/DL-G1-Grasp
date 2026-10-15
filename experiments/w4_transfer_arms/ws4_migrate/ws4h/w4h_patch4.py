#!/usr/bin/env python3
"""W4h patch 4: stiffen the temporary cube fixture weld (rep_ext_w1 only).
'.002 1' measured ~200 N/m effective -> the cube sags ~10mm under 1-2N pad forces while
welded, destroying the seat. '.0002 1' = 10x stiffer. Marked variant (W4h)."""
from pathlib import Path
import hashlib
SG = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_w1/rep/sonic_grasp.py')
src = SG.read_text()
old = "ET.SubElement(equality,'weld',name='w4h_cube_fixture',body1='red_cube',solref='.002 1')"
assert src.count(old) == 1, 'anchor'
src = src.replace(old, "ET.SubElement(equality,'weld',name='w4h_cube_fixture',body1='red_cube',solref='.0002 1')")
SG.write_text(src)
print('weld solref .002->.0002 OK sha256=%s' % hashlib.sha256(src.encode()).hexdigest())
