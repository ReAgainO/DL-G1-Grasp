import json, sys, warnings
import numpy as np
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
sys.path.insert(0, str(M / 'ws4h'))
from ws4h_seat2 import Rig2
edge = 80.
arm = [0.1217, 0.226, -0.4558, 0.7972, -0.5068, -0.3276, -0.1141]
hand = [0.9312, 0.0965, -0.2678, 1.0864, 1.2481, 0.1926, 0.9506]
rig = Rig2(edge)
aq = np.clip(np.array(arm), rig.m.jnt_range[rig.ja[22:29], 0] + .002, rig.m.jnt_range[rig.ja[22:29], 1] - .002)
hq = np.clip(np.array(hand), rig.m.jnt_range[rig.hj, 0] + 1e-9, rig.m.jnt_range[rig.hj, 1] - 1e-9)
r = rig.probe(aq, hq)
print('START2 audit gaps_mm', np.round(np.array(r['gap']) * 1e3, 3).tolist(), 'relz', np.round([x[2] * 1e3 for x in r['rel']], 1).tolist(),
      'palm', round(r['palm'] * 1e3, 1), 'body', r['body_min'][0], round(r['body_min'][1] * 1e3, 1), 'tab', round(r['table_d'] * 1e3, 1), 'span', round(r['span'] * 1e3, 1))
preset = dict(cube_pos=[float(x) for x in r['cf']], arm_q=[float(x) for x in aq], weld=True, freeze_hand=True, skip_to_close=True, settle_s=0.5,
              note='W4h W1S whisper-clamp START2 edge=80mm: thumb/index pressed on top, middle 1.33mm under bottom face; pads %s mm; palm %.1fmm; body %s@%.1fmm design_ok=True' % (
                  np.round(np.array(r['gap']) * 1e3, 3).tolist(), r['palm'] * 1e3, r['body_min'][0], r['body_min'][1] * 1e3))
open(str(M / 'ws4h/presets') + '/preset_w1s_80_whisper2.json', 'w').write(json.dumps(preset, indent=1) + '\n')
open(str(M / 'ws4h/grips') + '/grip_w1s_80_whisper2.json', 'w').write(json.dumps(dict(grip_target_rad=[round(float(x), 6) for x in hq]), indent=1) + '\n')
print('written preset/grip whisper2')
