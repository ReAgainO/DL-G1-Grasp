#!/usr/bin/env python3
"""W4g envelope-grip FK design probe. READ-ONLY on rep_base
(PYTHONDONTWRITEBYTECODE=1 must be set so imports do not write __pycache__).

Loads the baseline b25_12_04 model (right-hand collision mask applied), takes the
ACTUAL wrist pose at the first CLOSE frame, and evaluates candidate 7-joint
'envelope' closed-hand configs by FK in the wrist frame.

Wrist placement rule = the runtime arm target (pinch_geometry + surface_capture):
put grasp_geometry.contact_frame(config, cube_R, opponent=2) at the cube centre.
  contact_frame = middle_pad - n*(extent + pad_radius - 0.5mm),  n = (mid-thumb)/|.|
  extent = support function of the box in direction n (cube_R = I here), i.e.
  half*(|nx|+|ny|+|nz|).
=> positions of every hand point RELATIVE TO THE CUBE CENTRE depend only on the
config and on the wrist rotation R (identical across cells by construction).

Outputs: model masks, baseline FK, candidate table for 25/35/80/100mm cubes with
pad gaps (positive=clearance, negative=penetration) and a random-search short
list for 80mm.
"""
import sys, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')

B = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
SRC = B / 'rep_base/rep/out/b25_12_04'
sys.path.insert(0, str(B / 'rep_base/rep'))
from grasp_geometry import contact_frame  # read-only import, cross-check only

m = mujoco.MjModel.from_xml_path(str(SRC / 'scene.xml'))
d = mujoco.MjData(m)
hands = np.arange(36, 43)
hj = m.actuator_trnid[hands, 0]
hq = m.jnt_qposadr[hj]
names = [m.joint(int(j)).name for j in hj]
PADS = ('right_thumb_fingertip', 'right_index_fingertip', 'right_middle_fingertip')
pads = [m.geom(n).id for n in PADS]
cube = m.body('red_cube').id
wrist = m.body('right_wrist_yaw_link').id
cube_half_live = float(m.geom_size[m.geom('red_cube_geom').id, 0])

print('== model facts ==')
print('hand joint order:', names)
print('joint ranges:', [[round(x, 4) for x in r] for r in m.jnt_range[hj].tolist()])
print('pad radii m:', [round(float(m.geom_size[g, 0]), 6) for g in pads])
print('live cube half (b25 scene):', cube_half_live)

GTY = {0: 'plane', 1: 'hfield', 2: 'sphere', 3: 'capsule', 4: 'ellipsoid', 5: 'cylinder', 6: 'box', 7: 'mesh'}

def gname(i):
    if m.geom_type[i] == 7:
        dq = int(m.geom_dataid[i])
        return m.mesh(dq).name if dq >= 0 else '(mesh?)'
    return m.geom(i).name or '(unnamed)'

def mesh_of(i):
    if m.geom_type[i] == 7 and int(m.geom_dataid[i]) >= 0:
        return m.mesh(int(m.geom_dataid[i])).name
    return '-'

print('-- right-arm geom masks (name, body, type, contype, conaffinity) --')
handplink = 0
for i in range(m.ngeom):
    b = int(m.geom_bodyid[i])
    bn = m.body(b).name or ''
    if bn.startswith('right_'):
        nm = m.geom(i).name or '(unnamed)'
        if bn.startswith('right_hand_') or 'wrist' in bn:
            print('  %-30s %-28s %-6s c=%d a=%d size=%s' % (
                nm, bn, GTY.get(int(m.geom_type[i]),'?'), m.geom_contype[i], m.geom_conaffinity[i],
                np.round(m.geom_size[i], 5).tolist()))
        else:
            handplink += 1
print('  (other right_* geoms not shown: %d)' % handplink)
print('-- wrist-body geoms (palm candidates) --')
for i in range(m.ngeom):
    if int(m.geom_bodyid[i]) == wrist:
        print('  geom %-28s mesh=%s type=%s c=%d a=%d pos_local=%s' % (
            gname(i), mesh_of(i),
            GTY.get(int(m.geom_type[i]),'?'), m.geom_contype[i], m.geom_conaffinity[i],
            np.round(m.geom_pos[i], 4).tolist()))

tr = np.load(SRC / 'trajectory.npz', allow_pickle=True)
ph = [str(p) for p in tr['phase']]
i0 = ph.index('CLOSE')
q = tr['qpos'][i0].copy()
d.qpos[:] = q
mujoco.mj_forward(m, d)
p_w = d.xpos[wrist].copy()
R = d.xmat[wrist].reshape(3, 3).copy()
cube_c = d.xpos[cube].copy()
cube_R = d.xmat[cube].reshape(3, 3).copy()
print('\n== baseline CLOSE entry (b25_12_04, frame %d) ==' % i0)
print('wrist pos m:', np.round(p_w, 5).tolist())
print('wrist R (rows = palm local x/y/z axes expressed in world):')
print(np.round(R, 4))
print('cube centre:', np.round(cube_c, 5).tolist(), 'cube_R (should be ~I):')
print(np.round(cube_R, 3))

# palm proxy geoms: the two mesh geoms of right_hand_palm_link on the wrist body
palm_gids = []
for i in range(m.ngeom):
    if int(m.geom_bodyid[i]) == wrist:
        mns = mesh_of(i)
        if 'palm' in mns:
            palm_gids.append(i)
print('palm proxy geom ids:', palm_gids, 'count', len(palm_gids))

link_bodies = ['right_hand_thumb_0_link', 'right_hand_thumb_1_link', 'right_hand_thumb_2_link',
               'right_hand_index_0_link', 'right_hand_index_1_link',
               'right_hand_middle_0_link', 'right_hand_middle_1_link']
link_ids = [m.body(n).id for n in link_bodies]

def fk_local(qh):
    """return dict of wrist-frame local coords for pads/palm/link origins"""
    d.qpos[:] = q
    d.qpos[hq] = np.clip(qh, m.jnt_range[hj, 0] + 1e-9, m.jnt_range[hj, 1] - 1e-9)
    mujoco.mj_forward(m, d)
    out = dict(pads=[R.T @ (d.geom_xpos[g] - p_w) for g in pads],
               palm=[R.T @ (d.geom_xpos[g] - p_w) for g in palm_gids],
               links=[R.T @ (d.xpos[b] - p_w) for b in link_ids])
    return out

def pad_gap(rel, s, r):
    """sphere pad at 'rel' vs axis-aligned box half s centred at origin.
    positive = surface clearance, negative = penetration."""
    dx = np.abs(rel) - s
    out = np.clip(dx, 0.0, None)
    if out.max() > 0:
        return float(np.linalg.norm(out) - r)
    return float(-(r + float(np.min(-dx))))

def evaluate(qh, s, Ruse=R, verbose=True, tag=''):
    lo = fk_local(qh)
    pt, pi, pm = lo['pads']
    v = pm - pt
    L = float(np.linalg.norm(v))
    if L < .005:
        return None
    nhat = v / L
    nw = Ruse @ nhat
    extent = s * float(np.abs(nw).sum())
    r = float(m.geom_size[pads[2], 0])
    offset = extent + r - .0005
    cf_local = pm - nhat * offset
    # positions relative to cube centre (world axes, cube_R = I)
    relp = [Ruse @ (p - cf_local) for p in lo['pads']]
    relpalm = [Ruse @ (p - cf_local) for p in lo['palm']]
    rellink = [Ruse @ (p - cf_local) for p in lo['links']]
    gaps = [pad_gap(relp[i], s, float(m.geom_size[pads[i], 0])) for i in range(3)]
    palm_top_clear = min(float(p[2]) for p in relpalm) - s if relpalm else float('nan')
    palm_xy = np.mean([p[:2] for p in relpalm], axis=0) if relpalm else np.array([np.nan, np.nan])
    link_in = [float(np.max(np.abs(p) - s)) for p in rellink]  # >0 = outside box, <0 = origin inside
    if verbose:
        print('  [%s] q=%s' % (tag, np.round(qh, 4).tolist()))
        print('      n_world=%s  n.x=%+.3f  thumb-mid span=%.1fmm  thumb-idx=%.1f idx-mid=%.1f' % (
            np.round(nw, 3).tolist(), float(nw[0]), L * 1e3,
            float(np.linalg.norm(lo['pads'][1] - lo['pads'][0])) * 1e3,
            float(np.linalg.norm(lo['pads'][2] - lo['pads'][1])) * 1e3))
        for i, k in enumerate(['thumb', 'index', 'middle']):
            print('      %-6s rel_cube=%s mm  gap=%+.2f mm' % (
                k, np.round(relp[i] * 1e3, 1).tolist(), gaps[i] * 1e3))
        print('      palm  xy_off=%s mm  z_above_top=%+.1f mm  (proxy=%d geoms)' % (
            np.round(palm_xy * 1e3, 1).tolist(), palm_top_clear * 1e3, len(relpalm)))
        print('      link-origin max(|rel|-s): %s mm (>0 = outside)' % (
            np.round([x * 1e3 for x in link_in], 1).tolist()))
    return dict(nw=nw, L=L, relp=relp, gaps=gaps, palm_top_clear=palm_top_clear,
                palm_xy=palm_xy, link_in=link_in, cf_local=cf_local)

CAND = {
    'OPEN':           np.array([0., -.70, -2., 1.40, .08, 1.40, .08]),
    'recipeA_pinch':  np.array([0., -.60, -.88, 1.40, .08, 1.40, .08]),
    'real_mirror':    np.array([-0.0151, -0.6207, -0.6749, 0.9594, 1.4810, 0.9738, 1.4879]),
    'E1_open_thumb':  np.array([0., -.70, -2.0, 1.40, 0.00, 1.40, 0.00]),
    'E2_mid_curl':    np.array([0., -.70, -1.70, 1.40, 0.25, 1.40, 0.25]),
    'E3_more_curl':   np.array([0., -.65, -1.40, 1.40, 0.55, 1.40, 0.55]),
    'E4_adduct':      np.array([0., -.70, -2.0, 1.55, 0.00, 1.55, 0.00]),
    'E5_thumb1_up':   np.array([0., -.35, -1.90, 1.40, 0.00, 1.40, 0.00]),
}

for s, edgemm in [(.0125, 25), (.0175, 35), (.040, 80), (.050, 100)]:
    print('\n===== cube edge %dmm (half %.4f) =====' % (edgemm, s))
    for k, qh in CAND.items():
        print(' -- candidate %s (in-range=%s)' % (k, bool(((qh >= m.jnt_range[hj, 0]).all() and (qh <= m.jnt_range[hj, 1]).all()))))
        evaluate(qh, s, tag=k)

# cross-check contact_frame formula on the 35mm template at the SAME wrist pose
print('\n== cross-check contact_frame (35mm) vs inline formula ==')
for k in ('recipeA_pinch', 'real_mirror'):
    lo = fk_local(CAND[k])
    pt, pi, pm = lo['pads']
    nhat = (pm - pt) / np.linalg.norm(pm - pt)
    d.qpos[:] = q
    d.qpos[hq] = CAND[k]
    mujoco.mj_forward(m, d)
    try:
        cf_world = contact_frame(m, d, cube_R, opponent=2)
        est = p_w + R @ (pm - nhat * (float(cube_half_live) * float(np.abs((cube_R.T @ (R @ nhat))).sum()) + float(m.geom_size[pads[2], 0]) - .0005))
        print('  %s cf_ref=%s inline=%s |d|=%.3fmm' % (k, np.round(cf_world, 5).tolist(), np.round(est, 5).tolist(), float(np.linalg.norm(cf_world - est)) * 1e3))
    except Exception as e:
        print('  %s ref raised %r' % (k, e))

# ---------- random search for 80mm and 100mm ----------
print('\n== random search ==')
rng = np.random.default_rng(20261009)
for s, edgemm in [(.040, 80), (.050, 100)]:
    lo_b = np.array([-.72, -2.05, -.10, -.05, 0.00, -.05, 0.00])
    hi_b = np.array([-.30, -0.60, 1.75, 1.80, 1.30, 1.80, 1.30])
    best = []
    n_try = 0
    for _ in range(6000):
        qh = lo_b + rng.random(7) * (hi_b - lo_b)
        res = evaluate(qh, s, verbose=False)
        if res is None:
            continue
        n_try += 1
        gaps = np.array(res['gaps'])
        # want all three pads at ~ -0.4mm (touch with slight preload)
        c_pad = float(np.sum((gaps + 0.0004) ** 2))
        # n mostly +x (middle pad on the far side, thumb near side)
        c_n = (1.0 - float(res['nw'][0])) * 2.0
        # palm above the top face, and xy-aligned over the cube centre
        c_palm = max(0.0, (0.008 - res['palm_top_clear'])) + float(np.linalg.norm(res['palm_xy']))
        # thumbs/index/middle z spread at similar height (wrap, not vertical spear)
        c_v = float(abs(res['relp'][0][2] - res['relp'][1][2]) + abs(res['relp'][1][2] - res['relp'][2][2])) * 0.5
        # penalise link origins entering the box
        c_link = sum(max(0.0, -x) for x in res['link_in']) * 2.0
        cost = c_pad + c_n + c_palm + c_v + c_link
        if len(best) < 6 or cost < best[-1][0]:
            best.append((cost, qh.copy(), gaps.copy(), res['palm_top_clear'], res['palm_xy'].copy(), res['nw'].copy(), res['L']))
            best.sort(key=lambda t: t[0])
            best = best[:6]
    print(' --- best %d of %d valid samples for edge %dmm' % (len(best), n_try, edgemm))
    for cost, qh, gaps, ptc, pxy, nw, L in best:
        print('   cost=%.5f q=%s' % (cost, np.round(qh, 4).tolist()))
        print('       gaps_mm=%s palm_top=%+.1f palm_xy=%s n=%s span=%.1fmm' % (
            np.round(gaps * 1e3, 2).tolist(), ptc * 1e3, np.round(pxy * 1e3, 1).tolist(), np.round(nw, 3).tolist(), L * 1e3))
        evaluate(qh, s, verbose=True, tag='verify')
print('\nDONE')
