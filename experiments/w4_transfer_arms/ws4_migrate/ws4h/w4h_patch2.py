#!/usr/bin/env python3
"""W4h W1S patch 2: optional arm-preset (W4H_PRESET_JSON['arm_q'], 7 right-arm joints)
replaces the neutral arm reference at load, so the init pose / SETTLE hold / seat FK all
use it. Absent => inert. Applies to rep_ext_w1 only."""
from pathlib import Path
import hashlib
SG = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_w1/rep/sonic_grasp.py')
src = SG.read_text()
old = " neutral=neutral_body(m,s.DEFAULT_ANGLES,neutral_shoulder_offset)\n"
assert src.count(old) == 1, 'anchor count'
new = (" neutral=neutral_body(m,s.DEFAULT_ANGLES,neutral_shoulder_offset)\n"
       " if W4H_PRESET is not None and W4H_PRESET.get('arm_q') is not None: # W4h W1S (marked): optional arm pre-pose (7 right-arm joints) for the preset-seat protocol\n"
       "  _w4h_armq=[float(v) for v in W4H_PRESET['arm_q']]\n"
       "  assert len(_w4h_armq)==7,'W4h arm_q must hold 7 values'\n"
       "  neutral[arm]=np.asarray(_w4h_armq)\n"
       "  print('W4H_PRESET_ARM_Q '+json.dumps(_w4h_armq),flush=True)\n")
src = src.replace(old, new)
SG.write_text(src)
print('arm_q patch OK sha256=%s' % hashlib.sha256(src.encode()).hexdigest())
