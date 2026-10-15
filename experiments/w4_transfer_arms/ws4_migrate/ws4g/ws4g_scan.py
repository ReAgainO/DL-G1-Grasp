#!/usr/bin/env python3
"""W4g envelope-grip target scan v3: map the thumb reachability frontier for a
two-sided press on a large cube. READ-ONLY on rep_base.

For each (thumb_0/1/2, index/middle_0/1) print span, n, thumb/middle/index pad
positions relative to the cube centre (under the runtime cf placement), gaps for
80mm, the implied wrist position relative to the cube centre and the palm bbox
lowest point. Only rows with span>=92mm are printed (the 80mm two-sided press
needs >=99mm).
"""
import sys, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')

B = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
SRC = B / 'rep_base/rep/out/b25_12_04'
m = mujoco.MjModel.from_xml_path(str(SRC / 'scene.xml'))
d = mujoco.MjData(m)
hands = np.arange(36, 43)
hj = m.actuator_trnid[hands, 0]
hq = m.jnt_qposadr[hj]
PADS = ('right_thumb_fingertip', 'right_index_fingertip', 'right_middle_fingertip')
pads = [m.geom(n).id for n in PADS]
wrist = m.body('right_wrist_yaw_link').id

tr = np.load(SRC / 'trajectory.npz', allow_pickle=True)
ph = [str(p) for p in tr['phase']]
i0f = ph.index('CLOSE')
q = tr['qpos'][i0f].copy()
d.qpos[:] = q
mujoco.mj_forward(m, d)
p_w = d.xpos[wrist].copy()
R = d.xmat[wrist].reshape(3, 3).copy()

palm_gid = None
for i in range(m.ngeom):
    if int(m.geom_bodyid[i]) == wrist and m.geom_type[i] == 7:
        if 'palm' in m.mesh(int(m.geom_dataid[i])).name:
            palm_gid = i
            break
mgid = int(m.geom_dataid[palm_gid])
vadr, vnum = int(m.mesh_vertadr[mgid]), int(m.mesh_vertnum[mgid])
pv = np.asarray(m.mesh_vert[vadr:vadr + vnum, :3]).copy()
bbmin, bbmax = pv.min(axis=0), pv.max(axis=0)
corners = np.array([[a, b, c] for a in (bbmin[0], bbmax[0]) for b in (bbmin[1], bbmax[1]) for c in (bbmin[2], bbmax[2])])
d.qpos[:] = q
d.qpos[hq] = np.array([0., -.70, -2., 1.40, .08, 1.40, .08])
mujoco.mj_forward(m, d)
gp, gm = d.geom_xpos[palm_gid].copy(), d.geom_xmat[palm_gid].reshape(3, 3).copy()
palm_corners_local = np.array([R.T @ (gp + gm @ c - p_w) for c in corners])

def hand_local(qh):
    d.qpos[:] = q
    d.qpos[hq] = np.clip(qh, m.jnt_range[hj, 0] + 1e-9, m.jnt_range[hj, 1] - 1e-9)
    mujoco.mj_forward(m, d)
    return [R.T @ (d.geom_xpos[g] - p_w) for g in pads]

def gap(rel, s, r=0.010):
    dx = np.abs(rel) - s
    out = np.clip(dx, 0.0, None)
    if out.max() > 0:
        return float(np.linalg.norm(out) - r)
    return float(-(r + float(np.min(-dx))))

S = 0.040
r = 0.010
rows = []
for t0 in np.arange(-0.6, 0.61, 0.1):
    for t1 in [-0.75, -0.70, -0.65, -0.60, -0.55]:
        for t2 in [-2.05, -1.95, -1.85, -1.75, -1.65]:
            for i0 in [1.30, 1.40, 1.50]:
                for i1 in [0.0, 0.10, 0.20]:
                    qh = np.array([t0, t1, t2, i0, i1, i0, i1])
                    lp = hand_local(qh)
                    v = lp[2] - lp[0]
                    L = float(np.linalg.norm(v))
                    if L < 0.092:
                        continue
                    nhat = v / L
                    nw = R @ nhat
                    extent = S * float(np.abs(nw).sum())
                    offset = extent + r - .0005
                    cf_local = lp[2] - nhat * offset
                    relp = [R @ (p - cf_local) for p in lp]
                    relpalm = np.array([R @ (p - cf_local) for p in palm_corners_local])
                    wr = -R @ cf_local
                    g = [gap(relp[i], S) for i in range(3)]
                    rows.append((L * 1e3, np.round(nw, 3), np.round(qh, 4), np.round(relp[0] * 1e3, 1),
                                 np.round(relp[2] * 1e3, 1), np.round(relp[1] * 1e3, 1),
                                 np.round(g, 2), np.round(wr * 1e3, 1), float(relpalm[:, 2].min() - S)))
print('rows with span>=92mm: %d' % len(rows))
rows.sort(key=lambda x: -x[0])
print('span_mm  n_world            q(thumb0,1,2,idx0,idx1)         thumb_rel_mm        middle_rel_mm       index_rel_mm        gaps(mm)            wrist_rel_mm       palmzmin-top')
for span, nw, qh, t_rel, m_rel, i_rel, g, wr, pz in rows[:60]:
    print('%.1f  %-20s %-32s %-19s %-19s %-19s %-20s %-19s %+.1f' % (
        span, str(nw.tolist()), str([round(float(x), 2) for x in qh]), str(t_rel.tolist()), str(m_rel.tolist()),
        str(i_rel.tolist()), str(g.tolist()), str(wr.tolist()), pz * 1e3))
print('\nDONE')
