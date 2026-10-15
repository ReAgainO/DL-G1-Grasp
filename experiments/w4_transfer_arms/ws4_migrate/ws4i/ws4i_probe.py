import json, sys, warnings, numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
sys.path.insert(0, str(M/'rep_ext_w1'/'rep')); sys.path.insert(0, str(M/'ws4i'))
from source_physics_core import PADS, OPEN
from neutral_pose import neutral_body
import sonic_v11 as s
scenep, presp, gripp = sys.argv[1], sys.argv[2], sys.argv[3]
preset = json.loads(Path(presp).read_text()); grip = json.loads(Path(gripp).read_text())
m = mujoco.MjModel.from_xml_path(scenep); d = mujoco.MjData(m)
edge = 2*m.geom_size[m.geom('red_cube_geom').id,0]*1e3
cubeb = m.body('red_cube').id; cube_g = m.geom('red_cube_geom').id
pad_ids = [m.geom(n).id for n in PADS]
hj = m.actuator_trnid[np.arange(36,43),0]; hq = m.jnt_qposadr[hj]
ja = np.asarray(m.actuator_trnid[:29,0],dtype=int); aq = m.jnt_qposadr[ja]
cq = int(m.jnt_qposadr[int(m.body('red_cube').jntadr[0])])
arm = np.asarray(preset['arm_q']); hand = np.asarray(grip['grip_target_rad'])
neutral = neutral_body(m, s.DEFAULT_ANGLES, .2); neutral[22:29] = np.clip(arm, m.jnt_range[ja[22:29],0]+.002, m.jnt_range[ja[22:29],1]-.002)
hand = np.clip(hand, m.jnt_range[hj,0]+1e-9, m.jnt_range[hj,1]-1e-9)
d.qpos[:] = 0; d.qpos[:3] = [0,0,.788740]; d.qpos[3:7] = [1,0,0,0]
d.qpos[aq] = neutral; d.qpos[hq] = hand
mujoco.mj_forward(m, d)
cpos = np.asarray(preset['cube_pos'])
d.qpos[cq:cq+3] = cpos; d.qpos[cq+3:cq+7] = [1,0,0,0]; mujoco.mj_forward(m, d)
cc = d.xpos[cubeb].copy()
print('edge=%.1fmm pad_rad=%.1fmm cube_center=%s' % (edge, m.geom_size[pad_ids[0],0]*1e3, np.round(cc,5).tolist()))
print('ncon=%d' % d.ncon)
for i,g in enumerate(pad_ids):
    p = d.geom_xpos[g].copy()
    gap = mujoco.mj_geomDistance(m, d, g, cube_g, .05, None)
    print('pad%d %-28s center=%s  center-cube=%s mm  gap=%.2fmm' % (i, m.geom(g).name, np.round(p,5).tolist(), np.round((p-cc)*1e3,1).tolist(), gap*1e3))
for k in range(d.ncon):
    c = d.contact[k]; g1,g2 = int(c.geom1), int(c.geom2)
    other = g2 if g1==cube_g else g1
    if cube_g not in (g1,g2): continue
    fr = np.asarray(c.frame).reshape(3,3)
    row0 = fr[0,:].copy(); col0 = fr[:,0].copy()
    pc = d.geom_xpos[other].copy()
    def orient(n):
        return n if float(n @ (cc-pc)) >= 0 else -n
    print('  contact g1=%s g2=%s dist=%.3fmm pos=%s' % (m.geom(g1).name[:18], m.geom(g2).name[:18], c.dist*1e3, np.round(np.asarray(c.pos),5).tolist()))
    print('     row0=%s -> on-cube %s (n_z=%.2f)' % (np.round(row0,2).tolist(), np.round(orient(row0),2).tolist(), orient(row0)[2]))
    print('     col0=%s -> on-cube %s (n_z=%.2f)' % (np.round(col0,2).tolist(), np.round(orient(col0),2).tolist(), orient(col0)[2]))
