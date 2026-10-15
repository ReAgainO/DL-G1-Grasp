#!/usr/bin/env python3
"""W4g ENV envelope-config search v5: optimize the HAND-WRAP geometry directly with
mj_geomDistance (segments/palm/pads vs the cube), not just pad-vs-face targets.

Runtime facts used: the arm places contact_frame(cfg)=cube centre, where
contact_frame = middle_pad - n*(s*sum|n| + r - .5mm), n=(middle-thumb)/|.|. The hand
joints then HOLD the injected static config. So a config = a fixed wrap layout.

Objective per candidate (world frame after moving the cube body to cf):
  * thumb_2 / index_1 / middle_1 collision meshes engaged at [-1.5mm, +0.5mm];
  * palm collision mesh within [0, +4mm] (support/掌面);
  * wrap spread: the three segment CENTRES span both y-sides of the cube (>=.25s);
  * no deep penetration of any hand-chain collision geom (>= -2mm);
  * finger-table guard: segments not inside the table top;
  * pads not above the top face; wrist_rel.z high enough; n_y<0 preferred.

Writes ws4g_env_candidates.json (top-8 per size) and prints a readout.
READ-ONLY wrt rep_ext_env sources; scratch scenes under ws4g/scratch/.
"""
import json, time, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')

M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
AR = M / 'rep_ext_env'
B25 = M / 'rep_base/rep/out/b25_12_04'
import sys
sys.path.insert(0, str(AR / 'rep'))
import sonic_grasp as sg

PADS = ('right_thumb_fingertip', 'right_index_fingertip', 'right_middle_fingertip')
SEG_BODIES = ('right_hand_thumb_2_link', 'right_hand_index_1_link', 'right_hand_middle_1_link')
CHAIN_BODIES = ('right_hand_thumb_0_link', 'right_hand_thumb_1_link', 'right_hand_thumb_2_link',
                'right_hand_index_0_link', 'right_hand_index_1_link',
                'right_hand_middle_0_link', 'right_hand_middle_1_link')

def log(*a):
    print(*a, flush=True)

def build_scene(edge_mm, cx, cy):
    out = M / 'ws4g' / 'scratch' / ('envsearch_e%g' % edge_mm)
    if out.exists():__import__('shutil').rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    return sg.scene_and_cal(AR / 'rep', out, False, True, False, False, .24, float(edge_mm), float(cx), float(cy), 0., 0)[0]

class Rig:
    def __init__(self, edge_mm, cx=.285, cy=-.138):
        self.scn = build_scene(edge_mm, cx, cy)
        self.m = mujoco.MjModel.from_xml_path(str(self.scn))
        self.d = mujoco.MjData(self.m)
        m = self.m
        self.cube = m.geom('red_cube_geom').id
        self.pad_ids = [m.geom(n).id for n in PADS]
        self.hj = m.actuator_trnid[np.arange(36, 43), 0]
        self.hq = m.jnt_qposadr[self.hj]
        self.jid = int(m.body('red_cube').jntadr[0]); self.qa = int(m.jnt_qposadr[self.jid])
        self.table = m.geom('table_top').id
        # collision proxies (group 0) per body; palm = biggest mesh on the wrist body
        def group0(bn):
            bid = m.body(bn).id
            return [g for g in range(m.ngeom) if int(m.geom_bodyid[g]) == bid and int(m.geom_group[g]) == 0]
        self.seg = {bn: group0(bn) for bn in SEG_BODIES}
        self.chain = {}
        for bn in CHAIN_BODIES:
            self.chain[bn] = group0(bn)
        wrist_bid = m.body('right_wrist_yaw_link').id
        wg = [g for g in range(m.ngeom) if int(m.geom_bodyid[g]) == wrist_bid and int(m.geom_group[g]) == 0]
        wg.sort(key=lambda g: -float(m.geom_size[g, 2]))
        self.palm = wg[0]
        tr = np.load(B25 / 'trajectory.npz', allow_pickle=True)
        ph = [str(p) for p in tr['phase']]
        self.q0 = tr['qpos'][ph.index('CLOSE')].copy()
        d = self.d
        d.qpos[:] = self.q0
        mujoco.mj_forward(m, d)
        self.wrist = m.body('right_wrist_yaw_link').id
        self.p_w = d.xpos[self.wrist].copy()
        self.R = d.xmat[self.wrist].reshape(3, 3).copy()

    def eval(self, qh, s):
        m, d = self.m, self.d
        d.qpos[:] = self.q0
        d.qpos[self.hq] = np.clip(np.asarray(qh), m.jnt_range[self.hj, 0] + 1e-9, m.jnt_range[self.hj, 1] - 1e-9)
        mujoco.mj_forward(m, d)
        p = [d.geom_xpos[g].copy() for g in self.pad_ids]
        v = p[2] - p[0]
        L = float(np.linalg.norm(v))
        n = v / L
        cf = p[2] - n * (s * float(np.abs(n).sum()) + .010 - .0005)
        d.qpos[self.qa:self.qa + 3] = cf
        d.qpos[self.qa + 3:self.qa + 7] = [1., 0., 0., 0.]
        mujoco.mj_forward(m, d)
        D = {}
        for bn in SEG_BODIES:
            D[bn] = min(mujoco.mj_geomDistance(m, d, g, self.cube, .06, None) for g in self.seg[bn])
        dpalm = mujoco.mj_geomDistance(m, d, self.palm, self.cube, .06, None)
        dtable = min(mujoco.mj_geomDistance(m, d, g, self.table, .06, None) for bn in SEG_BODIES for g in self.seg[bn])
        # worst penetration over the whole chain (level-2 view)
        dwell = 0.
        for bn in CHAIN_BODIES:
            for g in self.chain[bn]:
                dd = mujoco.mj_geomDistance(m, d, g, self.cube, .03, None)
                if dd < 0: dwell = min(dwell, dd)
        relp = [p[i] - cf for i in range(3)]
        relpalm = d.geom_xpos[self.palm] - cf
        segc = {bn: d.xpos[m.body(bn).id].copy() - cf for bn in SEG_BODIES}
        ys = np.array([segc[bn][1] for bn in SEG_BODIES])
        wr = -self.R @ cf
        return dict(q=qh.copy(), n=n, L=L, relp=relp, dpalm=float(dpalm), dtable=float(dtable), dwell=float(dwell),
                    D=D, ys=ys, wrist_rel=wr, palm_rel=relpalm)

    def cost(self, r, s):
        c = 0.
        wseg = {SEG_BODIES[0]: 60., SEG_BODIES[1]: 30., SEG_BODIES[2]: 30.}
        for bn, w in wseg.items():
            d = r['D'][bn]
            if d < 0:
                e = min(0., d + .0015)          # want [-1.5mm, +0.5mm]
            else:
                e = max(0., d - .0005)
            c += w * e * e * 1e6
        e = r['dpalm']
        c += 12. * (min(0., e + 0.) if e < 0 else max(0., e - .004)) ** 2 * 1e6
        if r['dwell'] < -.002:
            c += 400. * (r['dwell'] + .002) ** 2 * 1e6
        if r['dtable'] < 0:
            c += 100. * r['dtable'] ** 2 * 1e6
        # wrap spread: segment centres on both y-sides
        c += 30. * max(0., .25 * s - r['ys'].max()) ** 2 * 1e6
        c += 30. * max(0., r['ys'].min() + .25 * s) ** 2 * 1e6
        # pads not above the top face
        for p in r['relp']:
            c += 8. * max(0., p[2] - (s - .001)) ** 2 * 1e6
        # wrist height
        c += 4. * max(0., (s + .045) - float(r['wrist_rel'][2])) ** 2 * 1e6
        # n direction preference
        c += .02 * ((1. + r['n'][1]) ** 2 + r['n'][0] ** 2 + .3 * r['n'][2] ** 2)
        return c

def main():
    rng = np.random.default_rng(20261009)
    out = {}
    for edge, s in ((35, .0175), (80, .040), (100, .050)):
        rig = Rig(edge)
        boxlo = np.array([-1.0, -0.75, -2.09, -0.15, 0.0, -0.15, 0.0])
        boxhi = np.array([1.0, 0.0, -0.05, 1.83, 1.0, 1.83, 1.0])
        seeds = [np.array([0., -.60, -.88, 1.40, .08, 1.40, .08]),
                 np.array([-.2, -.75, -1.25, 1.45, .15, 1.45, .15]),
                 np.array([-.5, -.75, -2.05, 1.30, 0., 1.30, 0.]),
                 np.array([-.6, -.75, -2.05, 1.30, 0., 1.30, 0.]),
                 np.array([-.1, -.65, -1.2, 1.3, .3, 1.3, .3]),
                 np.array([-.3, -.75, -1.6, 1.4, .1, 1.4, .1])]
        N = 15000
        best = []
        t0 = time.time()
        for k in range(N + len(seeds)):
            if k < len(seeds):
                qh = seeds[k]
            else:
                u = rng.random(7)
                qh = boxlo + u * (boxhi - boxlo)
                if k % 2 == 0:
                    qh = np.array([rng.uniform(-.75, .15), rng.uniform(-.75, -.45), rng.uniform(-2.09, -1.2),
                                   rng.uniform(.6, 1.75), rng.uniform(0., .6), rng.uniform(.6, 1.75), rng.uniform(0., .6)])
            r = rig.eval(qh, s)
            c = rig.cost(r, s)
            best.append((c, r))
        best.sort(key=lambda x: x[0])
        log('\n===== edge %dmm (s=%.4f) %d evals %.0fs =====' % (edge, s, N + len(seeds), time.time() - t0))
        keep = []
        for c, r in best[:8]:
            log('cost=%.5f q=%s span=%.1f n=%s' % (c, [round(float(x), 3) for x in r['q']], r['L'] * 1e3, np.round(r['n'], 3).tolist()))
            log('   D(mm): t2=%+.1f i1=%+.1f m1=%+.1f palm=%+.1f dwell=%+.1f table=%+.1f' % (
                r['D'][SEG_BODIES[0]] * 1e3, r['D'][SEG_BODIES[1]] * 1e3, r['D'][SEG_BODIES[2]] * 1e3,
                r['dpalm'] * 1e3, r['dwell'] * 1e3, r['dtable'] * 1e3))
            log('   seg_y_mm=%s wrist_rel=%s pad gaps=%s' % (
                np.round(r['ys'] * 1e3, 1).tolist(), np.round(r['wrist_rel'] * 1e3, 1).tolist(),
                [round(float(np.linalg.norm(np.clip(np.abs(p) - s, 0, None)) - .010 if np.abs(p).max() > s else -(.010 + float(np.min(s - np.abs(p)))), 4) * 1e3, 2) for p in r['relp']]))
            keep.append(dict(edge=edge, q=[float(x) for x in r['q']], cost=float(c),
                             D_mm=[round(float(r['D'][bn]) * 1e3, 2) for bn in SEG_BODIES],
                             palm_mm=round(float(r['dpalm']) * 1e3, 2), span_mm=round(r['L'] * 1e3, 1)))
        out[edge] = keep
    Path(M / 'ws4g' / 'ws4g_env_candidates.json').write_text(json.dumps(out, indent=1))
    log('\nWROTE', M / 'ws4g' / 'ws4g_env_candidates.json')
    log('DONE')

if __name__ == '__main__':
    main()
