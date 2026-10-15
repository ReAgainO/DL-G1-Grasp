import json, sys, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
sys.path.insert(0, str(M / 'ws4h'))
from ws4h_seat2 import Rig2
from ws4h_seat import gap_box, OPEN
from source_physics_core import PADS
for edge in [float(x) for x in sys.argv[1:]] or [80.]:
    rig = Rig2(edge)
    preset = json.loads(open(str(M / 'ws4h/presets') + '/preset_w1s_%g.json' % edge).read())
    grip = json.loads(open(str(M / 'ws4h/grips') + '/grip_w1s_%g.json' % edge).read())
    m, d = rig.m, rig.d
    neutral = rig.neutral0.copy(); neutral[22:29] = np.asarray(preset['arm_q'])
    d.qpos[:] = 0; d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]
    d.qpos[rig.aq] = neutral; d.qpos[rig.hq] = OPEN
    cq = rig.cq
    d.qpos[cq:cq + 3] = np.asarray(preset['cube_pos']); d.qpos[cq + 3:cq + 7] = [1., 0., 0., 0.]
    mujoco.mj_forward(m, d)
    s = rig.s
    pads = [(PADS[i], gap_box(d.geom_xpos[rig.pad_ids[i]] - np.asarray(preset['cube_pos']), s, .010) * 1e3) for i in range(3)]
    ch = []
    for bn in rig.chain:
        for g in rig.chain[bn]:
            ch.append((bn, float(mujoco.mj_geomDistance(m, d, g, rig.cube, .1, None)) * 1e3))
    wp = [(m.geom(g).name or '#%d' % g, float(mujoco.mj_geomDistance(m, d, g, rig.cube, .1, None)) * 1e3) for g in rig.wrist_geoms]
    bp = min(((bn, float(mujoco.mj_geomDistance(m, d, g, rig.cube, .1, None)) * 1e3) for bn, g in rig.body_geoms), key=lambda x: x[1])
    print('edge=%g OPEN-hand at seat: pad_gaps_mm=%s chain_min=%s@%.2f wrist=%s body_min=%s@%.2f ncon=%d' % (
        edge, [(n, round(v, 2)) for n, v in pads], min(ch, key=lambda x: x[1])[0], min(v for _, v in ch), wp, bp[0], bp[1], d.ncon))
    # contacts involving the cube
    cc = []
    for k in range(d.ncon):
        c = d.contact[k]
        g1, g2 = int(c.geom1), int(c.geom2)
        if rig.cube in (g1, g2):
            o = g2 if g1 == rig.cube else g1
            cc.append((m.geom(o).name or '#%d' % o, m.body(int(m.geom_bodyid[o])).name, round(float(c.dist) * 1e3, 2)))
    print('   cube contacts at t0:', cc)
