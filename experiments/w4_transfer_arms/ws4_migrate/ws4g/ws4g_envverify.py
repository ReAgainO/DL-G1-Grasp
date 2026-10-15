#!/usr/bin/env python3
"""W4g ENV verify: for the chosen configs, print full contact pairs (cube/table/other)
at levels 0/1/2 plus the L1-body distances. Read-only; scratch under ws4g/scratch.
Usage: ws4g_envverify.py  -> ws4g_envverify.out
"""
import json, sys, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')

M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
AR = M / 'rep_ext_env'
B25 = M / 'rep_base/rep/out/b25_12_04'
sys.path.insert(0, str(AR / 'rep'))
import sonic_grasp as sg

PADS = ('right_thumb_fingertip', 'right_index_fingertip', 'right_middle_fingertip')
CFGS = [
    (35, [0.42, -0.2, -0.8, 1.7, 0.05, 1.7, 0.05], 'fist shared'),
    (80, [0.42, -0.2, -0.8, 1.7, 0.05, 1.7, 0.05], 'v5c top1'),
    (100, [0.4188, -0.0826, -0.9816, 1.648, 0.2547, 1.648, 0.2547], 'v5c top1'),
]

def log(*a):
    print(*a, flush=True)

def build(level, edge):
    out = M / 'ws4g' / 'scratch' / ('verify_L%d_e%g' % (level, edge))
    if out.exists():
        import shutil; shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    return sg.scene_and_cal(AR / 'rep', out, False, True, False, False, .24, float(edge), .24 + edge * .0005 + .004, -.13, 0., level)[0]

def load(level, edge):
    m = mujoco.MjModel.from_xml_path(str(build(level, edge)))
    return m, mujoco.MjData(m)

def gap_box(rel, s, r=.010):
    dx = np.abs(rel) - s
    out = np.clip(dx, 0.0, None)
    if out.max() > 0:
        return float(np.linalg.norm(out) - r)
    return float(-(r + float(np.min(-dx))))

def label(m, g):
    nm = m.geom(g).name
    return '%s/%s#%d' % (m.body(int(m.geom_bodyid[g])).name, nm if nm else '-', g)

def main():
    tr = np.load(B25 / 'trajectory.npz', allow_pickle=True)
    ph = [str(p) for p in tr['phase']]
    q0 = tr['qpos'][ph.index('CLOSE')].copy()
    for edge, qh, note in CFGS:
        s = edge * .0005
        log('===== edge=%d %s q=%s' % (edge, note, [round(x, 4) for x in qh]))
        for level in (0, 1, 2):
            m, d = load(level, edge)
            cube = m.geom('red_cube_geom').id
            table = m.geom('table_top').id
            pads = [m.geom(n).id for n in PADS]
            hj = m.actuator_trnid[np.arange(36, 43), 0]
            hq = m.jnt_qposadr[hj]
            d.qpos[:] = q0
            d.qpos[hq] = np.clip(np.asarray(qh), m.jnt_range[hj, 0] + 1e-9, m.jnt_range[hj, 1] - 1e-9)
            mujoco.mj_forward(m, d)
            p = [d.geom_xpos[g].copy() for g in pads]
            v = p[2] - p[0]
            n = v / np.linalg.norm(v)
            cf = p[2] - n * (s * float(np.abs(n).sum()) + .010 - .0005)
            jid = int(m.body('red_cube').jntadr[0])
            qa = int(m.jnt_qposadr[jid])
            d.qpos[qa:qa + 3] = cf
            d.qpos[qa + 3:qa + 7] = [1., 0., 0., 0.]
            mujoco.mj_forward(m, d)
            if level == 0:
                for i, k in enumerate(['thumb', 'index', 'middle']):
                    log('   %-6s rel_cf=%s gap=%+.2fmm' % (k, np.round((p[i] - cf) * 1e3, 1).tolist(), gap_box(p[i] - cf, s) * 1e3))
            chain = set(g for g in range(m.ngeom) if m.body(int(m.geom_bodyid[g])).name.startswith('right_hand_') or m.body(int(m.geom_bodyid[g])).name == 'right_wrist_yaw_link')
            ncon = d.ncon
            pairs = []
            other = []
            for i in range(ncon):
                c = d.contact[i]
                g1, g2 = int(c.geom1), int(c.geom2)
                for a, b in ((g1, g2), (g2, g1)):
                    if a == cube and b in chain:
                        pairs.append('%s x cube d=%+.2fmm' % (label(m, b), c.dist * 1e3))
                    elif a == table and b in chain:
                        other.append('%s x table d=%+.2fmm' % (label(m, b), c.dist * 1e3))
            log('   [level %d] ncon=%d cube-contacts: %s' % (level, ncon, '; '.join(pairs) if pairs else 'NONE'))
            if other:
                log('   [level %d] table-contacts: %s' % (level, '; '.join(other)))
        log()

if __name__ == '__main__':
    main()
