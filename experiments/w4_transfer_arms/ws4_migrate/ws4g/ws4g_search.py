#!/usr/bin/env python3
"""W4g envelope-grip target search v4: per-cube-size random search over all 7
hand joints. READ-ONLY on rep_base.

Physics of the pipeline (established): the runtime arm puts
contact_frame(config)=cube centre with
contact_frame = middle_pad - n*(s*sum|n| + r - 0.5mm), n = (mid-thumb)/|.|.
So a hand config = a fixed multi-contact layout per cube size; the thumb/index
land wherever the kinematics allow. Search targets: all three pads touching the
80/100/35mm cube with ~0.5mm preload, pads in the lower half of the cube, no
deep penetrations, palm bbox not through the top face, n close to -y.
"""
import sys, warnings, time
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

lo_j = np.array(m.jnt_range[hj, 0]).copy()
hi_j = np.array(m.jnt_range[hj, 1]).copy()

def hand_local(qh):
    d.qpos[:] = q
    d.qpos[hq] = np.clip(qh, lo_j + 1e-9, hi_j - 1e-9)
    mujoco.mj_forward(m, d)
    return [R.T @ (d.geom_xpos[g] - p_w) for g in pads]

def gap(rel, s, r=0.010):
    dx = np.abs(rel) - s
    out = np.clip(dx, 0.0, None)
    if out.max() > 0:
        return float(np.linalg.norm(out) - r)
    return float(-(r + float(np.min(-dx))))

def evaluate(qh, s, lp=None):
    lp = hand_local(qh) if lp is None else lp
    v = lp[2] - lp[0]
    L = float(np.linalg.norm(v))
    nhat = v / L
    nw = R @ nhat
    extent = s * float(np.abs(nw).sum())
    offset = extent + 0.010 - .0005
    cf_local = lp[2] - nhat * offset
    relp = [R @ (p - cf_local) for p in lp]
    relpalm = np.array([R @ (p - cf_local) for p in palm_corners_local])
    wr = -R @ cf_local
    return dict(q=qh, nw=nw, L=L, relp=relp, palm_z_min=float(relpalm[:, 2].min()),
                palm_bbox_min=relpalm.min(axis=0), palm_bbox_max=relpalm.max(axis=0), wrist_rel=wr)

def cfun(res, s):
    relp = res['relp']
    g = np.array([gap(relp[i], s) for i in range(3)])
    c = 2.0 * min((g[0] + .0005) ** 2, .01) + 1.5 * min((g[1] + .0005) ** 2, .01) + 1.5 * min((g[2] + .0005) ** 2, .01)
    for gg in g:
        if gg < -.002:
            c += 5.0 * (gg + .002) ** 2
    for r_ in relp:
        c += 3.0 * max(0.0, r_[2] - .005) ** 2 + 0.5 * max(0.0, -.045 - r_[2]) ** 2
    nw = res['nw']
    c += 0.5 * ((1.0 + nw[1]) ** 2 + nw[0] ** 2 + nw[2] ** 2)
    c += 1.0 * max(0.0, s * .98 - res['palm_z_min'])
    c += 0.2 * max(0.0, (s + .045) - float(res['wrist_rel'][2]))
    return c, g

rng = np.random.default_rng(20261009)
for s, edge in [(.0175, 35), (.040, 80), (.050, 100)]:
    boxlo = np.array([-1.0, -0.75, -2.09, -0.15, 0.0, -0.15, 0.0])
    boxhi = np.array([1.0, 0.0, -0.05, 1.83, 1.0, 1.83, 1.0])
    # seed candidates incl. the observed frontier family
    seeds = [np.array([0., -.60, -.88, 1.40, .08, 1.40, .08]),
             np.array([0., -.55, -1.05, 1.40, 0.15, 1.40, 0.15]),
             np.array([-.2, -.75, -1.25, 1.45, .15, 1.45, .15]),
             np.array([-.5, -.75, -2.05, 1.40, .10, 1.40, .10]),
             np.array([-.6, -.75, -2.05, 1.30, .00, 1.30, .00])]
    N = 30000
    best = []
    t0 = time.time()
    for k in range(N + len(seeds)):
        if k < len(seeds):
            qh = seeds[k]
        else:
            u = rng.random(7)
            qh = boxlo + u * (boxhi - boxlo)
            # mix: also sample around the frontier
            if k % 3 == 0:
                qh = np.array([rng.uniform(-0.8, 0.2), rng.uniform(-0.75, -0.5), rng.uniform(-2.09, -1.6),
                               rng.uniform(1.1, 1.6), rng.uniform(0.0, 0.3), rng.uniform(1.1, 1.6), rng.uniform(0.0, 0.3)])
        res = evaluate(qh, s)
        c, g = cfun(res, s)
        best.append((c, qh.copy(), g.copy(), res['nw'].copy(), res['L'], res['relp'][0].copy(),
                     res['relp'][1].copy(), res['relp'][2].copy(), res['palm_z_min'], res['wrist_rel'].copy()))
    best.sort(key=lambda x: x[0])
    print('\n===== edge %dmm (s=%.4f)  %d evals in %.1fs =====' % (edge, s, N + len(seeds), time.time() - t0))
    for c, qh, g, nw, L, t_rel, i_rel, m_rel, pz, wr in best[:12]:
        print('cost=%.5f q=%s' % (c, np.round(qh, 3).tolist()))
        print('   span=%.1f n=%s gaps_mm=%s' % (L * 1e3, np.round(nw, 3).tolist(), np.round(g * 1e3, 2).tolist()))
        print('   thumb=%s index=%s middle=%s' % (np.round(t_rel * 1e3, 1).tolist(), np.round(i_rel * 1e3, 1).tolist(), np.round(m_rel * 1e3, 1).tolist()))
        print('   palm_z_min_vs_top=%+.1fmm wrist_rel=%s' % ((pz - s) * 1e3, np.round(wr * 1e3, 1).tolist()))
print('\nDONE')
