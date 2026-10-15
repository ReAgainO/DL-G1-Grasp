#!/usr/bin/env python3
"""W4h W1S seat3: cradle search. With freeze_close the CLOSE phase is passive, so the cube
may sit at contact_frame + delta (free offset) - search (arm 7, hand 7, delta 3) so that:
  * >=2 pads pressed [-1.5,-0.3]mm (CLOSE gate), palm/body/table clear;
  * after release the cube RESTS: >=1 pad contact with upward normal on the cube (n_z>=0.35)
    and the cube CoM projecting inside/at the support contacts (containment margin).
Writes preset_w1s_<edge>.json (with cube_pos, arm_q, design_gaps_mm, design contacts) and
grip_w1s_<edge>.json. Read-only wrt arm sources.
Usage: ws4h_seat3.py EDGE [NSURVEY]
"""
import json, sys, time, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
sys.path.insert(0, str(M / 'ws4h'))
from ws4h_seat import build, gap_box, band, hinge, PADS, OPEN
import sonic_grasp as sg
from grasp_geometry import contact_frame
from neutral_pose import neutral_body
import sonic_v11 as s

EDGE = float(sys.argv[1]) if len(sys.argv) > 1 else 80.
NS = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
OPPONENT = 2
ARM_SEED = [0.324751, 0.43786, -0.352404, 0.574001, -0.403848, -0.031974, 0.049799]
HAND_SEEDS = [
    [0.1217, 0.226, -0.4558, 0.7972, -0.5068, -0.3276, -0.1141],  # (arm of prior bests, hand varies)
]
HAND_SEED_Q = [
    [1.0472, 0.1205, -0.3478, 1.0164, 1.2881, 0.1826, 0.9186],   # prior clamp hand
    [0.9312, 0.0965, -0.2678, 1.0864, 1.2481, 0.1926, 0.9506],   # prior whisper hand
    [-0.0685, -0.1225, -0.1965, 0.8875, 0.478, 0.6805, 0.0],
    [0.42, -0.2, -0.8, 1.7, 0.05, 1.7, 0.05],
]
def log(*a): print(*a, flush=True)

class Rig3:
    def __init__(self, edge):
        self.m = m = mujoco.MjModel.from_xml_path(str(build(edge)))
        self.d = d = mujoco.MjData(m)
        self.s = edge * .0005
        self.cube = m.geom('red_cube_geom').id
        self.pad_ids = [m.geom(n).id for n in PADS]
        self.hj = m.actuator_trnid[np.arange(36, 43), 0]; self.hq = m.jnt_qposadr[self.hj]
        self.ja = np.asarray(m.actuator_trnid[:29, 0], dtype=int)
        self.aq = m.jnt_qposadr[self.ja]
        self.cq = int(m.jnt_qposadr[int(m.body('red_cube').jntadr[0])])
        self.cube_body = int(m.body('red_cube').jntadr[0])
        self.table = m.geom('table_top').id
        self.wrist = m.body('right_wrist_yaw_link').id
        def coll(bn):
            bid = m.body(bn).id
            return [g for g in range(m.ngeom) if int(m.geom_bodyid[g]) == bid and int(m.geom_group[g]) == 0 and (int(m.geom_contype[g]) or int(m.geom_conaffinity[g]))]
        self.wrist_geoms = coll('right_wrist_yaw_link')
        pelvis = m.body('pelvis').id
        robot = {pelvis}
        for i in range(1, m.nbody):
            if int(m.body_parentid[i]) in robot: robot.add(i)
        self.hand_bodies = [m.body(b).name for b in range(m.nbody) if (m.body(b).name or '').startswith('right_hand_')]
        self.chain = {bn: coll(bn) for bn in self.hand_bodies}
        self.body_geoms = []
        for b in sorted(robot):
            bn = m.body(b).name or ''
            if bn.startswith('right_hand_') or bn == 'right_wrist_yaw_link': continue
            self.body_geoms += [(bn, g) for g in coll(bn)]
        self.neutral0 = neutral_body(m, s.DEFAULT_ANGLES, .2)
        d.qpos[:] = 0; d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[self.aq] = self.neutral0; d.qpos[self.hq] = OPEN
        mujoco.mj_forward(m, d)
        self.table_top = float(d.geom_xpos[self.table, 2] + m.geom_size[self.table, 2])
        self.tpos = d.geom_xpos[self.table].copy(); self.tsize = m.geom_size[self.table].copy()
        log('RIG3 edge=%g body_geoms=%d table_top=%.4f' % (edge, len(self.body_geoms), self.table_top))

    def probe(self, arm, hand, delta):
        m, d = self.m, self.d
        arm = np.clip(np.asarray(arm, float), m.jnt_range[self.ja[22:29], 0] + .002, m.jnt_range[self.ja[22:29], 1] - .002)
        hand = np.clip(np.asarray(hand, float), m.jnt_range[self.hj, 0] + 1e-9, m.jnt_range[self.hj, 1] - 1e-9)
        delta = np.clip(np.asarray(delta, float), -.06, .06)
        neutral = self.neutral0.copy(); neutral[22:29] = arm
        d.qpos[:] = 0
        d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[self.aq] = neutral; d.qpos[self.hq] = hand
        mujoco.mj_forward(m, d)
        cf = contact_frame(m, d, d.xmat[self.cube_body].reshape(3, 3), opponent=OPPONENT).copy()
        cpos = cf + delta
        d.qpos[self.cq:self.cq + 3] = cpos; d.qpos[self.cq + 3:self.cq + 7] = [1., 0., 0., 0.]
        mujoco.mj_forward(m, d)
        r = dict(arm=arm, hand=hand, delta=delta.copy(), cf=cf, cpos=cpos, wrist=d.xpos[self.wrist].copy())
        r['rel'] = [d.geom_xpos[self.pad_ids[i]] - cpos for i in range(3)]
        r['gap'] = [float(mujoco.mj_geomDistance(m, d, self.pad_ids[i], self.cube, .05, None)) for i in range(3)]
        r['span'] = float(np.linalg.norm(d.geom_xpos[self.pad_ids[2]] - d.geom_xpos[self.pad_ids[0]]))
        r['palm'] = min(mujoco.mj_geomDistance(m, d, g, self.cube, .06, None) for g in self.wrist_geoms)
        r['body_min'] = min(((bn, float(mujoco.mj_geomDistance(m, d, g, self.cube, .12, None))) for bn, g in self.body_geoms), key=lambda x: x[1])
        r['table_d'] = float(mujoco.mj_geomDistance(m, d, self.table, self.cube, .12, None))
        cont = []
        for k in range(d.ncon):
            c = d.contact[k]
            g1, g2 = int(c.geom1), int(c.geom2)
            if self.cube not in (g1, g2): continue
            other = g2 if g1 == self.cube else g1
            n = np.asarray(c.frame).reshape(3, 3)[:, 0].copy()
            if g1 == self.cube: n = -n  # normal direction of the force ON the cube
            cont.append(dict(geom=other, body=m.body(int(m.geom_bodyid[other])).name, pad=other in self.pad_ids,
                             n=n.copy(), pos=np.asarray(c.pos).copy(), dist=float(c.dist)))
        r['contacts'] = cont
        r['pad_contacts'] = [c for c in cont if c['pad']]
        r['support'] = [c for c in r['pad_contacts'] if c['n'][2] >= 0.35]
        r['cage'] = [c for c in r['pad_contacts'] if abs(c['n'][2]) < 0.35]
        return r

    def cost(self, arm, hand, delta, arm_seed=ARM_SEED):
        try:
            r = self.probe(arm, hand, delta)
        except Exception:
            return 1e9
        g = [x * 1e3 for x in r['gap']]
        c = 300. * band(g[0], -1.8, -0.6) + 300. * band(g[1], -1.8, -0.6) + 300. * band(g[2], -1.8, -0.6)
        for x in g:
            if x < -2.2: c += 300. * (x + 2.2) ** 2
        c += 400. * hinge(0.3 - r['palm'] * 1e3) + 400. * hinge(5.0 - r['body_min'][1] * 1e3)
        c += 400. * hinge(2.0 - r['table_d'] * 1e3)
        nband = int(sum(-1.8 <= x <= -0.6 for x in g)); c -= 4000. * min(nband, 2)
        c += 150. * sum(max(0., -0.6 - x) ** 2 for x in g)
        nsup = len(r['support']); ncage = len(r['cage'])
        if nsup < 2: c += 20000. # W4h: the hold NEEDS >=2 upward supports, mandatory
        if nsup >= 2: c -= 2500.
        if nsup >= 1 and ncage >= 1: c -= 1000.
        # CoM containment of the supports (world xy; cube unrotated)
        com = r['cpos'][:2]
        if nsup >= 1:
            pts = np.array([c['pos'][:2] for c in r['support']])
            if len(pts) >= 3:
                margin = 1e9
                for i in range(len(pts)):
                    a, b2 = pts[i], pts[(i + 1) % len(pts)]
                    e = b2 - a; L = np.linalg.norm(e)
                    if L < 1e-9: continue
                    nrm = np.array([-e[1], e[0]]) / L
                    d_ = float(nrm @ (com - a))
                    # make sure the inside is positive: orient with the centroid
                    if float(nrm @ (pts.mean(axis=0) - a)) < 0: d_ = -d_
                    margin = min(margin, d_)
            elif len(pts) == 2:
                # distance from com to the segment, signed by... use negative distance to segment (want com ON the segment)
                a, b2 = pts
                e = b2 - a; L = np.linalg.norm(e)
                t = 0. if L < 1e-9 else float(np.clip(np.dot(com - a, e) / (L * L), 0, 1))
                margin = L * (0.5 - abs(t - 0.5)) if t in (0., 1.) else (L * 0.5 - abs(t - 0.5) * L) * 0.5
                margin = -float(np.linalg.norm(com - (a + t * e)))  # outside seg = negative
            else:
                margin = -float(np.linalg.norm(com - pts[0]))
            mm = margin * 1e3
            if mm >= 8.: c -= 2500.
            else: c += 150. * (8. - mm) ** 2
        c += 25. * hinge(20. - r['span'] * 1e3) + 25. * hinge(r['span'] * 1e3 - 175.)
        c += 5. * float(np.sum((np.asarray(arm) - np.asarray(arm_seed)) ** 2)) + 5. * float(np.sum(np.asarray(delta) ** 2 * 1e4))
        return c

    def descend(self, arm, hand, delta, arm_seed):
        arm = np.asarray(arm, float).copy(); hand = np.asarray(hand, float).copy(); delta = np.asarray(delta, float).copy()
        best = self.cost(arm, hand, delta, arm_seed)
        rounds = [('h', (.08, .03, .01, .004)), ('d', (.03, .012, .005, .002)), ('a', (.08, .03, .012)), ('h', (.02, .008)), ('d', (.008, .003))]
        for tag, steps in rounds:
            for step in steps:
                improved, guard = True, 0
                while improved and guard < 60:
                    improved, guard = False, guard + 1
                    vec = hand if tag == 'h' else delta if tag == 'd' else arm
                    for j in range(len(vec)):
                        for sgn in (1., -1.):
                            v2 = vec.copy(); v2[j] += sgn * step
                            a2, h2, d2 = (arm, v2, delta) if tag == 'h' else (arm, hand, v2) if tag == 'd' else (v2, hand, delta)
                            c = self.cost(a2, h2, d2, arm_seed)
                            if c < best - 1e-9:
                                if tag == 'h': hand = v2
                                elif tag == 'd': delta = v2
                                else: arm = v2
                                best, improved, vec = c, True, v2
        return arm, hand, delta, best

def main():
    t0 = time.time()
    rig = Rig3(EDGE)
    lo_a = rig.m.jnt_range[rig.ja[22:29], 0] + .0022; hi_a = rig.m.jnt_range[rig.ja[22:29], 1] - .0022
    lo_h = rig.m.jnt_range[rig.hj, 0] + 1e-6; hi_h = rig.m.jnt_range[rig.hj, 1] - 1e-6
    rng = np.random.RandomState(31)
    cands = []
    for hq in HAND_SEED_Q:
        cands.append((np.array(ARM_SEED), np.array(hq), np.zeros(3)))
    for i in range(NS):
        r = rng.rand()
        if r < .35:
            a = lo_a + (hi_a - lo_a) * rng.rand(7); h = lo_h + (hi_h - lo_h) * rng.rand(7)
        elif r < .7:
            a = np.clip(np.array(ARM_SEED) + rng.normal(0, .5, 7), lo_a, hi_a); h = lo_h + (hi_h - lo_h) * rng.rand(7)
        else:
            a = np.clip(np.array(ARM_SEED) + rng.normal(0, .3, 7), lo_a, hi_a)
            h = np.clip(np.array(HAND_SEED_Q[i % 4]) + rng.normal(0, .35, 7), lo_h, hi_h)
        delta = rng.uniform(-.045, .045, 3)
        cands.append((a, h, delta))
    scored = []
    for a, h, dlt in cands:
        scored.append((rig.cost(a, h, dlt), a, h, dlt))
    scored.sort(key=lambda x: x[0])
    log('survey %d wall=%.1fs best c=%.0f arm=%s delta=%s' % (len(scored), time.time() - t0, scored[0][0], np.round(scored[0][1], 3).tolist(), np.round(scored[0][3] * 1e3, 1).tolist()))
    best = None
    for k in range(min(5, len(scored))):
        c0, a0, h0, d0 = scored[k]
        a, h, dlt, c = rig.descend(a0, h0, d0, ARM_SEED)
        r = rig.probe(a, h, dlt)
        log('START%d c=%.1f arm=%s hand=%s d_mm=%s gaps=%s palm=%.1f body=%s@%.1f sup=%d cage=%d span=%.1f' % (
            k, c, np.round(a, 3).tolist(), np.round(h, 3).tolist(), np.round(dlt * 1e3, 1).tolist(),
            np.round(np.array(r['gap']) * 1e3, 2).tolist(), r['palm'] * 1e3, r['body_min'][0], r['body_min'][1] * 1e3,
            len(r['support']), len(r['cage']), r['span'] * 1e3))
        if best is None or c < best[3]: best = (a, h, dlt, c, r)
    a, h, dlt, c, r = best
    a = np.clip(a, lo_a, hi_a); h = np.clip(h, lo_h, hi_h)
    r = rig.probe(a, h, dlt); c = rig.cost(a, h, dlt, ARM_SEED)
    log('==== BEST cost=%.2f wall=%.1fs ====' % (c, time.time() - t0))
    log('arm_q=%s' % np.round(a, 6).tolist()); log('hand_q=%s' % np.round(h, 6).tolist())
    log('cf=%s delta_mm=%s cube_pos=%s' % (np.round(r['cf'], 5).tolist(), np.round(dlt * 1e3, 2).tolist(), np.round(r['cpos'], 5).tolist()))
    log('gaps_mm=%s palm=%.1fmm body=%s@%.1fmm table_d=%.1fmm span=%.1fmm' % (
        np.round(np.array(r['gap']) * 1e3, 2).tolist(), r['palm'] * 1e3, r['body_min'][0], r['body_min'][1] * 1e3, r['table_d'] * 1e3, r['span'] * 1e3))
    for c_ in r['pad_contacts']:
        log('   contact %s n=%s n_z=%.2f pos=%s' % (c_['body'], np.round(c_['n'], 2).tolist(), c_['n'][2], np.round(c_['pos'], 4).tolist()))
    fm = [(c_['body'], round(float(c_['dist']) * 1e3, 2)) for c_ in r['contacts']]
    log('all cube contacts (body, dist_mm): %s' % fm)
    hs = M / 'ws4h'
    preset = dict(cube_pos=[float(x) for x in r['cpos']], arm_q=[float(x) for x in a], weld=True, freeze_hand=True,
                  skip_to_close=True, settle_s=0.5, weld_release='LIFT',
                  design_gaps_mm=[round(float(x) * 1e3, 3) for x in r['gap']],
                  note='W4h W1S seat3 cradle edge=%gmm: cf+delta %s mm; pads %s mm; palm %.1f; body %s@%.1f; sup=%d cage=%d' % (
                      EDGE, np.round(dlt * 1e3, 2).tolist(), np.round(np.array(r['gap']) * 1e3, 2).tolist(), r['palm'] * 1e3,
                      r['body_min'][0], r['body_min'][1] * 1e3, len(r['support']), len(r['cage'])))
    (hs / 'presets' / ('preset_w1s_%g.json' % EDGE)).write_text(json.dumps(preset, indent=1) + '\n')
    (hs / 'grips' / ('grip_w1s_%g.json' % EDGE)).write_text(json.dumps(dict(grip_target_rad=[round(float(x), 6) for x in h]), indent=1) + '\n')
    audit = dict(edge_mm=EDGE, cost=c, arm_q=a.tolist(), hand_q=h.tolist(), cf_m=r['cf'].tolist(), delta_mm=(dlt * 1e3).tolist(), cube_pos_m=r['cpos'].tolist(),
                 pad_gap_mm=[float(x) * 1e3 for x in r['gap']], palm_mm=r['palm'] * 1e3, body_min=[r['body_min'][0], r['body_min'][1] * 1e3],
                 table_d_mm=r['table_d'] * 1e3, span_mm=r['span'] * 1e3,
                 pad_contacts=[dict(body=c_['body'], n=[float(x) for x in c_['n']], pos=[float(x) for x in c_['pos']], dist_mm=float(c_['dist']) * 1e3) for c_ in r['pad_contacts']],
                 other_contacts=[dict(body=c_['body'], dist_mm=float(c_['dist']) * 1e3) for c_ in r['contacts'] if not c_['pad']],
                 wall_s=time.time() - t0)
    (hs / ('seat3_audit_%g.json' % EDGE)).write_text(json.dumps(audit, indent=1) + '\n')
    log('WROTE preset/grip/audit (seat3) for edge=%g' % EDGE)

if __name__ == '__main__':
    main()
