#!/usr/bin/env python3
"""W4g envelope-grip target search v2 (design stage). READ-ONLY on rep_base.

Key facts from ws4g_probe.out (wrist rotation fixed by the pipeline):
  * runtime places the wrist so contact_frame(config) = cube centre, with
    contact_frame = middle_pad - n*(s*(|nx|+|ny|+|nz|) + r - 0.5mm), n=mid-thumb.
    => the middle pad ALWAYS ends exactly tangent-ish to the cube along n;
       a two-sided thumb+middle press needs span = offset + (s+r-0.5).
  * 80mm (s=40mm) => span >= ~99mm of the 101.8mm open span; 100mm needs ~119mm.
Optimises thumb_0/1/2 + (symmetric) index/middle 0/1 to press thumb on the
opposite y-face at low height, keep n ~ -y, and keep the palm (real mesh bbox)
above the top face. Prints the shortlist, detailed readouts, the OPEN-hand
clearance at the same wrist pose, and reuse on 25/35/80/100mm cubes.
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
cube = m.body('red_cube').id
wrist = m.body('right_wrist_yaw_link').id

tr = np.load(SRC / 'trajectory.npz', allow_pickle=True)
ph = [str(p) for p in tr['phase']]
i0 = ph.index('CLOSE')
q = tr['qpos'][i0].copy()
d.qpos[:] = q
mujoco.mj_forward(m, d)
p_w = d.xpos[wrist].copy()
R = d.xmat[wrist].reshape(3, 3).copy()

# ---- palm rigid bbox corners in the wrist frame (hand-joint independent) ----
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
print('palm mesh verts=%d bbox local half=%s wrist-local corner z range=[%.1f, %.1f]mm' % (
    vnum, np.round((bbmax - bbmin) / 2 * 1e3, 1).tolist(),
    palm_corners_local[:, 2].min() * 1e3, palm_corners_local[:, 2].max() * 1e3))

def hand_local(qh):
    d.qpos[:] = q
    d.qpos[hq] = np.clip(qh, m.jnt_range[hj, 0] + 1e-9, m.jnt_range[hj, 1] - 1e-9)
    mujoco.mj_forward(m, d)
    return [R.T @ (d.geom_xpos[g] - p_w) for g in pads]

def solve_frame(lp):
    """lp: 3 pad locals -> n, span, cf_local, and (rel derivables)"""
    pt, pi, pm = lp
    v = pm - pt
    L = float(np.linalg.norm(v))
    nhat = v / L
    return nhat, L, pi

def gap(rel, s, r=0.010):
    dx = np.abs(rel) - s
    out = np.clip(dx, 0.0, None)
    if out.max() > 0:
        return float(np.linalg.norm(out) - r)
    return float(-(r + float(np.min(-dx))))

def evaluate(qh, s, lc=None):
    lp = hand_local(qh) if lc is None else lc
    nhat, L, pi = solve_frame(lp)
    nw = R @ nhat
    extent = s * float(np.abs(nw).sum())
    offset = extent + 0.010 - .0005
    cf_local = lp[2] - nhat * offset
    relp = [R @ (p - cf_local) for p in lp]
    relpalm = np.array([R @ (p - cf_local) for p in palm_corners_local])
    return dict(q=qh, nw=nw, L=L, relp=relp, palm_z_min=float(relpalm[:, 2].min()),
                palm_bbox_min=relpalm.min(axis=0), palm_bbox_max=relpalm.max(axis=0))

def cost_of(res, s):
    relp = res['relp']
    g = np.array([gap(relp[i], s) for i in range(3)])  # + = clearance
    c = 3.0 * min((g[0] + .0004) ** 2, .004) + 2.0 * min((g[2] + .0004) ** 2, .004) \
        + 1.0 * min((g[1] + .0004) ** 2, .004)
    # index: penalise deep penetration harder, small reward for hovering close
    if g[1] < -.0015:
        c += 4.0 * (g[1] + .0015) ** 2
    # pad heights: want at or below +10mm
    c += 4.0 * sum(max(0.0, r_[2] - .010) ** 2 for r_ in relp)
    # n close to -y
    c += 1.5 * ((1.0 + res['nw'][1]) ** 2 + res['nw'][0] ** 2 + res['nw'][2] ** 2)
    # palm above the top face by >= 2mm
    c += 2.0 * max(0.0, (s - .002) - res['palm_z_min'])
    return c, g

print('\n== grid search (s=40mm) ==')
S = 0.040
best = []
n_ev = 0
for t0 in np.arange(-0.5, 0.55, 0.1):
    for t1 in np.arange(-0.75, -0.34, 0.05):
        for t2 in np.arange(-2.05, -1.19, 0.05):
            for i0 in [1.15, 1.30, 1.45, 1.60]:
                for i1 in [0.0, 0.15, 0.30, 0.45]:
                    qh = np.array([t0, t1, t2, i0, i1, i0, i1])
                    res = evaluate(qh, S)
                    c, g = cost_of(res, S)
                    n_ev += 1
                    best.append((c, qh.copy(), g.copy(), res['nw'].copy(), res['L'], res['palm_z_min']))
best.sort(key=lambda x: x[0])
print('evaluated %d candidates' % n_ev)

def report(qh, tag, sizes=(0.0125, 0.0175, 0.040, 0.050)):
    for s in sizes:
        res = evaluate(qh, s)
        relp = res['relp']
        print('  [%s s=%.4f edge=%3dmm] n=%s span=%.1fmm' % (
            tag, s, int(s * 2000), np.round(res['nw'], 3).tolist(), res['L'] * 1e3))
        for i, k in enumerate(['thumb', 'index', 'middle']):
            print('      %-6s rel=%8s mm gap=%+7.2f' % (
                k, np.round(relp[i] * 1e3, 1).tolist(), gap(relp[i], s) * 1e3))
        print('      palm bbox min=%s max=%s  z_min_vs_top=%+0.1fmm' % (
            np.round(res['palm_bbox_min'] * 1e3, 1).tolist(), np.round(res['palm_bbox_max'] * 1e3, 1).tolist(),
            (res['palm_z_min'] - s) * 1e3))

print('\n== shortlist top 10 ==')
for c, qh, g, nw, L, pz in best[:10]:
    print('cost=%.5f q=%s g(mm)=%s n=%s span=%.1f palm_z_min=%+.1fmm' % (
        c, np.round(qh, 4).tolist(), np.round(g * 1e3, 2).tolist(), np.round(nw, 3).tolist(), L * 1e3, pz * 1e3))

print('\n== detailed readout of top 3 ==')
for c, qh, g, nw, L, pz in best[:3]:
    print('== cand q=%s cost=%.5f' % (np.round(qh, 4).tolist(), c))
    report(qh, 'top')
    res_open = evaluate(np.array([0., -.70, -2., 1.40, .08, 1.40, .08]), S)
    print('  OPEN-hand same wrist pose (80mm): rel=%s gaps=%s' % (
        np.round(np.array(res_open['relp']) * 1e3, 1).tolist(),
        [round(gap(r_, S) * 1e3, 2) for r_ in res_open['relp']]))
print('\nDONE')
