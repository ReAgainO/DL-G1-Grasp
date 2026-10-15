import json, sys, os, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
os.environ['W4H_PRESET_JSON'] = str(M / 'ws4h/presets/preset_w1s_80_whisper2.json')
sys.path.insert(0, str(M / 'rep_ext_w1/rep'))
import sonic_grasp as sg
out = M / 'ws4h/scratch/weldtest'
if out.exists():
    import shutil; shutil.rmtree(out)
out.mkdir(parents=True, exist_ok=True)
scene = sg.scene_and_cal(M / 'rep_ext_w1/rep', out, False, True, False, False, .24, 80., .285, -.138, 0., 0)[0]
m = mujoco.MjModel.from_xml_path(str(scene))
print('neq', m.neq, 'eq name', mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_EQUALITY, 0))
print('eq_type', m.eq_type, 'eq_obj1id', m.eq_obj1id, 'eq_obj2id', m.eq_obj2id)
print('eq_data[0] anchor pos', m.eq_data[0][:3], 'quat', m.eq_data[0][3:7] if m.eq_type[0]==mujoco.mjtEq.mjEQ_WELD else '')
print('eq_solref', m.eq_solref, 'eq_active0', m.eq_active0)
preset = json.loads((M / 'ws4h/presets/preset_w1s_80_whisper2.json').read_text())
d = mujoco.MjData(m)
cube = m.body('red_cube')
cq = int(m.jnt_qposadr[int(cube.jntadr[0])])
# no control, just let physics resolve: cube should stay at preset if weld holds
for i in range(1500):
    mujoco.mj_step(m, d)
    if i % 250 == 0:
        print('step', i, 't=%.2f' % (i * m.opt.timestep), 'cube_z=%.5f' % d.xpos[cube.id][2], 'eq_active', d.eq_active[:])
print('final cube_xpos', np.round(d.xpos[cube.id], 5).tolist(), 'preset', np.round(preset['cube_pos'], 5).tolist())
