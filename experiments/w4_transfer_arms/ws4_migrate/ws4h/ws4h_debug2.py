import json, os, sys, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
sys.path.insert(0, str(M / 'ws4h'))
from ws4h_seat2 import Rig2, ARM_SEED
preset = json.loads((M / 'ws4h/presets/preset_w1s_80.json').read_text())
grip = json.loads((M / 'ws4h/grips/grip_w1s_80.json').read_text())
rig = Rig2(80.)
print('rig2 neutral0[:22]=', np.round(rig.neutral0[:22], 5).tolist())
print('rig2 neutral0[22:29]=', np.round(rig.neutral0[22:29], 5).tolist())
r = rig.probe(preset['arm_q'], grip['grip_target_rad'])
print('probe2 cf=', np.round(r['cf'], 6).tolist())
print('probe2 wrist=', np.round(r['wrist'], 5).tolist())
print('probe2 applied_arm=', np.round(r['arm_q'], 6).tolist())
print('probe2 gaps_mm=', np.round(np.array(r['gap']) * 1e3, 2).tolist())
# also: exact same probe but with arm_q == ARM_SEED
r2 = rig.probe(ARM_SEED, grip['grip_target_rad'])
print('probe2(ARM_SEED) wrist=', np.round(r2['wrist'], 5).tolist(), 'cf=', np.round(r2['cf'], 5).tolist())
