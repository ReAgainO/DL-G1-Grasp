import json, os, sys, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
AR = M / 'rep_ext_w1'
sys.path.insert(0, str(AR / 'rep'))
import sonic_grasp as sg
from grasp_geometry import contact_frame
from neutral_pose import neutral_body
import sonic_v11 as s
from source_physics_core import PADS, OPEN

preset = json.loads((M / 'ws4h/presets/preset_w1s_80.json').read_text())
grip = json.loads((M / 'ws4h/grips/grip_w1s_80.json').read_text())
os.environ['W4H_PRESET_JSON'] = str(M / 'ws4h/presets/preset_w1s_80.json')
import importlib
importlib.reload(sg)  # pick up env-provided preset for scene_and_cal
out = M / 'ws4h/scratch/dbg_e80'
if out.exists():
    import shutil; shutil.rmtree(out)
out.mkdir(parents=True, exist_ok=True)
scene = sg.scene_and_cal(AR / 'rep', out, False, True, False, False, .24, 80., .285, -.138, 0., 0)[0]
m = mujoco.MjModel.from_xml_path(str(scene))
d = mujoco.MjData(m)
aq = m.jnt_qposadr[m.actuator_trnid[:29, 0]]
hj = m.actuator_trnid[np.arange(36, 43), 0]; hq = m.jnt_qposadr[hj]
neutral = neutral_body(m, s.DEFAULT_ANGLES, .2)
neutral[22:29] = np.asarray(preset['arm_q'])
# --- run path: lines 255..344 ---
d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]; d.qpos[aq] = neutral; d.qpos[hq] = OPEN
mujoco.mj_forward(m, d)
print('runpath arm_qpos=', np.round(d.qpos[aq[22:29]], 6).tolist())
print('runpath wrist=', np.round(d.xpos[m.body('right_wrist_yaw_link').id], 5).tolist())
close_hand = np.asarray(grip['grip_target_rad'], float)
d.qpos[hq] = close_hand.copy(); mujoco.mj_forward(m, d)
geo = mujoco.MjData(m); geo.qpos[:] = d.qpos; geo.qpos[hq] = close_hand; mujoco.mj_forward(m, geo)
seat_run = contact_frame(m, geo, d.xmat[m.body('red_cube').id].reshape(3, 3), opponent=2).copy()
print('seat_run=', np.round(seat_run, 6).tolist())
# --- seat2 probe path ---
d2 = mujoco.MjData(m)
neutral2 = neutral_body(m, s.DEFAULT_ANGLES, .2); neutral2[22:29] = np.asarray(preset['arm_q'])
d2.qpos[:] = 0
d2.qpos[:3] = [0, 0, .788740]; d2.qpos[3:7] = [1, 0, 0, 0]
d2.qpos[aq] = neutral2; d2.qpos[hq] = close_hand
mujoco.mj_forward(m, d2)
print('seat2path arm_qpos=', np.round(d2.qpos[aq[22:29]], 6).tolist())
print('seat2path wrist=', np.round(d2.xpos[m.body('right_wrist_yaw_link').id], 5).tolist())
seat2 = contact_frame(m, d2, d2.xmat[m.body('red_cube').id].reshape(3, 3), opponent=2).copy()
print('seat2=', np.round(seat2, 6).tolist())
print('JSON=', np.round(np.asarray(preset['cube_pos']), 6).tolist())
print('drift run=%.3fmm seat2=%.3fmm' % (np.linalg.norm(seat_run - np.asarray(preset['cube_pos'])) * 1e3, np.linalg.norm(seat2 - np.asarray(preset['cube_pos'])) * 1e3))
print('pads run=', [np.round(geo.geom_xpos[g], 5).tolist() for g in [m.geom(n).id for n in PADS]])
print('pads s2 =', [np.round(d2.geom_xpos[g], 5).tolist() for g in [m.geom(n).id for n in PADS]])
