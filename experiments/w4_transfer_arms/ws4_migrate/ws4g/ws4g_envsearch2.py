#!/usr/bin/env python3
"""W4g ENV envelope-config search v5b: hybrid objective = explicit pad-vs-face
engagement (thumb on +y face, middle on -y face, index shallow) PLUS mesh wrap via
mj_geomDistance (thumb_2/index_1/middle_1 >= -1.5mm, palm in [0,+4mm], all other
chain geoms >= -2mm, table clear). 5-dim symmetric parameterization
[thumb0,thumb1,thumb2,index0,index1] (middle = index). Coordinate descent from
structured seeds + perturbed restarts.

Writes ws4g_env_candidates.json {edge: [top...]}. Read-only wrt rep_ext_env sources.
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
SEG = ('right_hand_thumb_2_link', 'right_hand_index_1_link', 'right_hand_middle_1_link')
GUARD = ('right_hand_thumb_0_link', 'right_hand_thumb_1_link', 'right_hand_index_0_link', 'right_hand_middle_0_link')
LO = np.array([-1.0472, -1.0472, -2.0944, -0.192, 0.0])
HI = np.array([1.0472, 0.7243, 0.0, 1.8326, 2.0944])

def log(*a):
    print(*a, flush=True)

def build_scene(edge_mm, cx, cy):
    out = M / 'ws4g' / 'scratch' / ('envsearch2_e%g' % edge_mm)
    if out.exists():
        import shutil; shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    return sg.scene_and_cal(AR / 'rep', out, False, True, False, False, .24, float(edge_mm), float(cx), float(cy), 0., 0)[0]

def gap_box(rel, s, r=.010):
    dx = np.abs(rel) - s
    out = np.clip(dx, 0.0, None)
    if out.max() > 0:
        return float(np.linalg.norm(out) - r)
    return float(-(r + float(np.min(-dx))))

class Rig:
    def __init__(self, edge_mm, cx=None, cy=-.13):
        cx = .24 + edge_mm * .0005 + .004 if cx is None else cx
        self.scn = build_scene(edge_mm, cx, cy)
        m = mujoco.MjModel.from_xml_path(str(self.scn))
        self.m = m
        self.d = mujoco.MjData(m)
        self.cube = m.geom('red_cube_geom').id
        self.pad_ids = [m.geom(n).id for n in PADS]
        self.hj = m.actuator_trnid[np.arange(36, 43), 0]
        self.hq = m.jnt_qposadr[self.hj]
        self.jid = int(m.body('red_cube').jntadr[0])
        self.qa = int(m.jnt_qposadr[self.jid])
        self.table = m.geom('table_top').id
        def group0(bn):
            bid = m.body(bn).id
            return [g for g in range(m.ngeom) if int(m.geom_bodyid[g]) == bid and int(m.geom_group[g]) == 0]
        self.seg = {bn: group0(bn) for bn in SEG}
        self.guard = {bn: group0(bn) for bn in GUARD}
        wrist_bid = m.body('right_wrist_yaw_link').id
        wg = [g for g in range(m.ngeom) if int(m.geom_bodyid[g]) == wrist_bid and int(m.geom_group[g]) == 0]
        wg.sort(key=lambda g: -float(m.geom_size[g, 2]))
        self.palm = wg[0]
        tr = np.load(B25 / 'trajectory.npz', allow_pickle=True)
        ph = [str(p) for p in tr['phase']]
        self.q0 = tr['qpos'][ph.index('CLOSE')].copy()
        self.d.qpos[:] = self.q0
        mujoco.mj_forward(m, self.d)
        self.wrist = m.body('right_wrist_yaw_link').id
        self.R = self.d.xmat[self.wrist].reshape(3, 3).copy()
        self.p_w = self.d.xpos[self.wrist].copy()

    def q7(self, q5):
        return np.array([q5[0], q5[1], q5[2], q5[3], q5[4], q5[3], q5[4]])

    def eval(self, q5, s):
        m, d = self.m, self.d
        qh = self.q7(np.clip(q5, LO, HI))
        d.qpos[:] = self.q0
        d.qpos[self.hq] = np.clip(qh, m.jnt_range[self.hj, 0] + 1e-9, m.jnt_range[self.hj, 1] - 1e-9)
        mujoco.mj_forward(m, d)
        p = [d.geom_xpos[g].copy() for g in self.pad_ids]
        v = p[2] - p[0]
        L = float(np.linalg.norm(v))
        n = v / L
        cf = p[2] - n * (s * float(np.abs(n).sum()) + .010 - .0005)
        d.qpos[self.qa:self.qa + 3] = cf
        d.qpos[self.qa + 3:self.qa + 7] = [1., 0., 0., 0.]
        mujoco.mj_forward(m, d)
        D = {bn: min(mujoco.mj_geomDistance(m, d, g, self.cube, .06, None) for g in self.seg[bn]) for bn in SEG}
        dpalm = mujoco.mj_geomDistance(m, d, self.palm, self.cube, .06, None)
        dguard = min(mujoco.mj_geomDistance(m, d, g, self.cube, .04, None) for bn in GUARD for g in self.guard[bn])
        dtable = min(mujoco.mj_geomDistance(m, d, g, self.table, .04, None) for bn in SEG for g in self.seg[bn])
        relp = [p[i] - cf for i in range(3)]
        return dict(q5=np.array(q5, float), n=n, L=L, relp=relp, D=D, dpalm=float(dpalm),
                    dguard=float(dguard), dtable=float(dtable), wrist_rel=self.p_w - cf)

    def cost(self, q5, s):
        r = self.eval(q5, s)
        c = 0.
        for i, w in ((0, 30.), (1, 15.), (2, 30.)):
            g = gap_box(r['relp'][i], s)
            e = min(0., g + .003) if g < 0 else max(0., g - .008)
            c += w * e * e * 1e6
        for bn, w in ((SEG[0], 50.), (SEG[1], 35.), (SEG[2], 35.)):
            dd = r['D'][bn]
            e = min(0., dd + .0025) if dd < 0 else max(0., dd - .001)
            c += w * e * e * 1e6
        e = r['dpalm']
        e = min(0., e + .002) if e < 0 else max(0., e - .004)
        c += 20. * e * e * 1e6
        c += 2. * max(0., -r['dguard'] - .035) ** 2 * 1e6
        c += 20. * max(0., -r['dtable'] - .006) ** 2 * 1e6
        c += 6. * max(0., (s + .045) - float(r['wrist_rel'][2])) ** 2 * 1e6
        sep = r['relp'][0][1] - r['relp'][2][1]
        c += 10. * max(0., .35 * s - sep) ** 2 * 1e6
        c += .5 * max(0., r['n'][1] + .3) ** 2
        return c, r

def refine(rig, s, q0, steps=(0.30, 0.12, 0.05)):
    q = np.clip(np.array(q0, float), LO, HI)
    c, _ = rig.cost(q, s)
    for st in steps:
        improved = True
        guard = 0
        while improved and guard < 60:
            improved = False
            guard += 1
            for k in range(5):
                for dv in (st, -st):
                    q2 = q.copy()
                    q2[k] = min(max(q2[k] + dv, LO[k]), HI[k])
                    c2, _ = rig.cost(q2, s)
                    if c2 < c - 1e-9:
                        q, c = q2, c2
                        improved = True
    return c, q

def main():
    rng = np.random.default_rng(20261009)
    out = {}
    for edge, s in ((35, .0175), (80, .040), (100, .050)):
        rig = Rig(edge)
        seeds = [
            [0., -.60, -.88, 1.40, .08],
            [-.2, -.75, -1.25, 1.45, .15],
            [-.4, -.72, -1.60, 1.40, .10],
            [-.5, -.75, -1.90, 1.35, .05],
            [-.6, -.75, -2.05, 1.30, .00],
            [-.3, -.65, -1.40, 1.50, .20],
            [-.15, -.70, -1.10, 1.55, .25],
            [-.45, -.70, -1.75, 1.45, .10],
            [-.35, -.75, -1.95, 1.20, .00],
            [-.55, -.70, -1.85, 1.30, .10],
            [-.25, -.60, -1.50, 1.60, .20],
            [-.05, -.70, -1.30, 1.40, .12],
        ]
        cand = []
        t0 = time.time()
        n_ev = 0
        for si, q0 in enumerate(seeds):
            c, q = refine(rig, s, q0)
            n_ev += 60 * 3
            cand.append((c, q.copy()))
            if si < 11:
                for _ in range(3):
                    qp = np.array(q0, float) + rng.normal(0, .18, 5)
                    c2, q2 = refine(rig, s, qp)
                    cand.append((c2, q2.copy()))
        cand.sort(key=lambda x: x[0])
        log('\n===== edge %dmm (s=%.4f)  %.0fs =====' % (edge, s, time.time() - t0))
        keep = []
        seen = 0
        for c, q5 in cand:
            c2, r = rig.cost(q5, s)
            qh = rig.q7(q5)
            rec = dict(edge=edge, q=[float(x) for x in qh], cost=float(c2),
                       D_mm=[round(float(r['D'][bn]) * 1e3, 2) for bn in SEG],
                       palm_mm=round(float(r['dpalm']) * 1e3, 2), guard_mm=round(float(r['dguard']) * 1e3, 2),
                       table_mm=round(float(r['dtable']) * 1e3, 2), span_mm=round(r['L'] * 1e3, 1),
                       pads_gap_mm=[round(gap_box(r['relp'][i], s) * 1e3, 2) for i in range(3)],
                       wrist_rel_mm=[round(float(x) * 1e3, 1) for x in r['wrist_rel']])
            log('cost=%9.1f q56=%s' % (c2, [round(float(x), 3) for x in q5]))
            log('   span=%.1f n=%s D(mm) t2=%+.1f i1=%+.1f m1=%+.1f palm=%+.1f guard=%+.1f table=%+.1f' % (
                r['L'] * 1e3, np.round(r['n'], 3).tolist(), r['D'][SEG[0]] * 1e3, r['D'][SEG[1]] * 1e3,
                r['D'][SEG[2]] * 1e3, r['dpalm'] * 1e3, r['dguard'] * 1e3, r['dtable'] * 1e3))
            log('   pad gaps(mm)=%s wrist_rel=%s' % (rec['pads_gap_mm'], rec['wrist_rel_mm']))
            keep.append(rec)
            seen += 1
            if seen >= 6:
                break
        out[edge] = keep
    Path(M / 'ws4g' / 'ws4g_env_candidates.json').write_text(json.dumps(out, indent=1))
    log('\nWROTE ws4g_env_candidates.json')
    log('DONE')

if __name__ == '__main__':
    main()
