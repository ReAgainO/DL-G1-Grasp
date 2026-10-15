#!/usr/bin/env python3
"""W4h W1S seat2: search hand config AND right-arm pre-pose (arm_q) at the init pose so
that the ALIGN-equilibrium seat (cf = contact_frame of the closed hand at that pose) is a
clean holdable cage: >=2 pads pressed, palm clear, cube clear of every other robot geom and
of the table. Writes preset_w1s_<edge>.json (with arm_q) + grip_w1s_<edge>.json.

Usage: ws4h_seat2.py EDGE [NSURVEY]
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
NS = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
OPPONENT = 2
ARM_SEED = [0.324751, 0.43786, -0.352404, 0.574001, -0.403848, -0.031974, 0.049799]  # b25 CLOSE frame
HAND_SEEDS = [
    [0.666, 0.223, -1.221, 1.8326, 0.025, 1.794, 0.158],   # seat1 best (cradle+side)
    [0.967, 0.358, -0.071, 0.791, 1.298, 0.644, 1.327],    # survey M1
    [-0.0685, -0.1225, -0.1965, 0.8875, 0.478, 0.6805, 0.0],  # survey M2
]

def log(*a): print(*a, flush=True)

class Rig2:
    def __init__(self, edge):
        self.m = m = mujoco.MjModel.from_xml_path(str(build(edge)))
        self.d = d = mujoco.MjData(m)
        self.s = edge * .0005
        self.cube = m.geom('red_cube_geom').id
        self.pad_ids = [m.geom(n).id for n in PADS]
        self.hj = m.actuator_trnid[np.arange(36, 43), 0]; self.hq = m.jnt_qposadr[self.hj]
        self.ja = np.asarray(m.actuator_trnid[:29, 0], dtype=int)  # TRUE joint ids (jnt_range index space)
        self.aq = m.jnt_qposadr[self.ja]
        self.cq = int(m.jnt_qposadr[int(m.body('red_cube').jntadr[0])])
        self.table = m.geom('table_top').id
        self.wrist = m.body('right_wrist_yaw_link').id
        def coll(bn):
            bid = m.body(bn).id
            return [g for g in range(m.ngeom) if int(m.geom_bodyid[g]) == bid and int(m.geom_group[g]) == 0 and (int(m.geom_contype[g]) or int(m.geom_conaffinity[g]))]
        self.wrist_geoms = coll('right_wrist_yaw_link')
        hand_bodies = [m.body(b).name for b in range(m.nbody) if (m.body(b).name or '').startswith('right_hand_')]
        self.seg = {bn: coll(bn) for bn in ('right_hand_thumb_2_link', 'right_hand_index_1_link', 'right_hand_middle_1_link')}
        self.chain = {bn: coll(bn) for bn in hand_bodies}
        pelvis = m.body('pelvis').id
        robot = {pelvis}
        for i in range(1, m.nbody):
            if int(m.body_parentid[i]) in robot: robot.add(i)
        self.body_geoms = []
        for b in sorted(robot):
            bn = m.body(b).name or ''
            if bn.startswith('right_hand_') or bn == 'right_wrist_yaw_link': continue
            self.body_geoms += [(bn, g) for g in coll(bn)]
        self.neutral0 = neutral_body(m, s.DEFAULT_ANGLES, .2)
        self.table_top = None
        d.qpos[:] = 0; d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[self.aq] = self.neutral0; d.qpos[self.hq] = OPEN
        mujoco.mj_forward(m, d)
        self.table_top = float(d.geom_xpos[self.table, 2] + m.geom_size[self.table, 2])
        self.tpos = d.geom_xpos[self.table].copy(); self.tsize = m.geom_size[self.table].copy()
        log('RIG2 edge=%g body_geoms=%d table_top=%.4f table_x=[%.3f,%.3f]' % (edge, len(self.body_geoms), self.table_top, self.tpos[0] - self.tsize[0], self.tpos[0] + self.tsize[0]))

    def probe(self, arm_q, hand_q):
        m, d = self.m, self.d
        arm_q = np.clip(np.asarray(arm_q, float), m.jnt_range[self.ja[22:29], 0] + .002, m.jnt_range[self.ja[22:29], 1] - .002)
        hand_q = np.clip(np.asarray(hand_q, float), m.jnt_range[self.hj, 0] + 1e-9, m.jnt_range[self.hj, 1] - 1e-9)
        neutral = self.neutral0.copy(); neutral[22:29] = arm_q
        d.qpos[:] = 0
        d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[self.aq] = neutral; d.qpos[self.hq] = hand_q
        mujoco.mj_forward(m, d)
        p = [d.geom_xpos[g].copy() for g in self.pad_ids]
        cf = contact_frame(m, d, d.xmat[m.body('red_cube').id].reshape(3, 3), opponent=OPPONENT).copy()
        d.qpos[self.cq:self.cq + 3] = cf; d.qpos[self.cq + 3:self.cq + 7] = [1., 0., 0., 0.]
        mujoco.mj_forward(m, d)
        r = dict(arm_q=arm_q.copy(), hand_q=hand_q.copy(), cf=cf, wrist=d.xpos[self.wrist].copy())
        r['rel'] = [p[i] - cf for i in range(3)]
        r['gap'] = [gap_box(r['rel'][i], self.s, float(m.geom_size[self.pad_ids[i], 0])) for i in range(3)]
        r['span'] = float(np.linalg.norm(p[2] - p[0]))
        r['palm'] = min(mujoco.mj_geomDistance(m, d, g, self.cube, .06, None) for g in self.wrist_geoms)
        r['segmin'] = min(min(mujoco.mj_geomDistance(m, d, g, self.cube, .06, None) for g in self.seg[bn]) for bn in self.seg)
        bd = [(bn, float(mujoco.mj_geomDistance(m, d, g, self.cube, .12, None))) for bn, g in self.body_geoms]
        r['body_min'] = min(bd, key=lambda x: x[1])
        r['table_d'] = float(mujoco.mj_geomDistance(m, d, self.table, self.cube, .12, None))
        r['cube_bottom'] = float(cf[2] - self.s)
        over = (abs(cf[0] - self.tpos[0]) <= self.tsize[0] - self.s + .001) and (abs(cf[1] - self.tpos[1]) <= self.tsize[1] - self.s + .001)
        r['over_table'] = bool(over)
        r['bottom_vs_table'] = float(r['cube_bottom'] - self.table_top)
        return r

    def cost(self, arm_q, hand_q, arm_seed):
        try:
            r = self.probe(arm_q, hand_q)
        except Exception:
            return 1e9
        g = [x * 1e3 for x in r['gap']]
        rz = [x[2] * 1e3 for x in r['rel']]
        c = 0.
        c += 600. * band(g[0], -0.25, -0.05) + 600. * band(g[1], -0.25, -0.05) + 600. * band(g[2], -0.25, -0.05)
        for x in g:
            if x < -0.40: c += 400. * (x + 0.40) ** 2
        c += 400. * hinge(0.3 - r['palm'] * 1e3)
        c += 200. * hinge(-1.2 - r['segmin'] * 1e3)
        c += 400. * hinge(5.0 - r['body_min'][1] * 1e3)
        c += 400. * hinge(2.0 - r['table_d'] * 1e3)
        if r['over_table']: c += 400. * hinge(5.0 - r['bottom_vs_table'] * 1e3)
        nband = int(sum(-0.25 <= x <= -0.05 for x in g)); c -= 4000. * min(nband, 2) + (2000. if nband >= 3 else 0.)
        nlow = int(sum(x <= -30 for x in rz)); nup = int(sum(x >= 30 for x in rz))
        c -= 1500. * min(nlow, 1); c -= 600. * min(nup, 1)
        top_band = any(-0.25 <= g[i] <= -0.05 and rz[i] >= 30 for i in range(3))
        bot_band = any(-0.25 <= g[i] <= -0.05 and rz[i] <= -35 for i in range(3))
        if top_band and bot_band: c -= 3000.
        c += 25. * hinge(20. - r['span'] * 1e3) + 25. * hinge(r['span'] * 1e3 - 170.)
        c += 8. * float(np.sum((np.asarray(arm_q) - np.asarray(arm_seed)) ** 2))
        return c

    def descend(self, arm_q, hand_q, arm_seed, rounds):
        arm_q = np.asarray(arm_q, float).copy(); hand_q = np.asarray(hand_q, float).copy()
        best = self.cost(arm_q, hand_q, arm_seed)
        for tag, steps in rounds:
            for step in steps:
                improved, guard = True, 0
                while improved and guard < 60:
                    improved, guard = False, guard + 1
                    vec, j_n = (hand_q, 7) if tag == 'h' else (arm_q, 7)
                    for j in range(j_n):
                        for sgn in (1., -1.):
                            v2 = vec.copy(); v2[j] += sgn * step
                            a2, h2 = (arm_q, v2) if tag == 'h' else (v2, hand_q)
                            c = self.cost(a2, h2, arm_seed)
                            if c < best - 1e-9:
                                if tag == 'h': hand_q = v2
                                else: arm_q = v2
                                best, improved, vec = c, True, v2
        return arm_q, hand_q, best

def main():
    t0 = time.time()
    rig = Rig2(EDGE)
    lo_a = rig.m.jnt_range[rig.ja[22:29], 0] + .0022; hi_a = rig.m.jnt_range[rig.ja[22:29], 1] - .0022
    log('ARM_JOINT_RANGES %s' % ([[round(x, 4) for x in r] for r in rig.m.jnt_range[rig.ja[22:29]].tolist()],))
    lo_h = rig.m.jnt_range[rig.hj, 0] + 1e-6; hi_h = rig.m.jnt_range[rig.hj, 1] - 1e-6
    rng = np.random.RandomState(21)
    cands = []
    for hs in HAND_SEEDS:
        cands.append((np.array(ARM_SEED), np.array(hs)))
    for i in range(NS):
        if i % 4 == 0:
            a = np.clip(np.array(ARM_SEED) + rng.normal(0, .45, 7), lo_a, hi_a)
            h = np.clip(np.array(HAND_SEEDS[i % 3]) + rng.normal(0, .40, 7), lo_h, hi_h)
        else:
            a = np.clip(np.array(ARM_SEED) + rng.normal(0, .18, 7), lo_a, hi_a)
            h = np.clip(np.array(HAND_SEEDS[i % 3]) + rng.normal(0, .30, 7), lo_h, hi_h)
        cands.append((a, h))
    scored = []
    for a, h in cands:
        scored.append((rig.cost(a, h, ARM_SEED), a, h))
    scored.sort(key=lambda x: x[0])
    log('survey %d done wall=%.1fs best=%s c=%.0f' % (len(scored), time.time() - t0, np.round(scored[0][1], 3).tolist(), scored[0][0]))
    rounds = [('h', (.08, .03, .01, .004)), ('a', (.10, .04, .015, .006)),
              ('h', (.03, .01, .004)), ('a', (.04, .015, .006)), ('h', (.015, .005))]
    best = None
    for k in range(min(4, len(scored))):
        c0, a0, h0 = scored[k]
        aq, hq, c = rig.descend(a0, h0, ARM_SEED, rounds)
        r = rig.probe(aq, hq)
        log('START%d c0=%.0f -> c=%.1f arm=%s hand=%s gaps=%s relz=%s palm=%.1f body=%s@%.1f tab=%.1f span=%.1f' % (
            k, c0, c, np.round(aq, 4).tolist(), np.round(hq, 4).tolist(), np.round(np.array(r['gap']) * 1e3, 2).tolist(),
            np.round([x[2] * 1e3 for x in r['rel']], 1).tolist(), r['palm'] * 1e3, r['body_min'][0], r['body_min'][1] * 1e3, r['table_d'] * 1e3, r['span'] * 1e3))
        if best is None or c < best[2]: best = (aq, hq, c, r)
    aq, hq, c, r = best
    aqc = np.clip(aq, lo_a, hi_a); hqc = np.clip(hq, lo_h, hi_h)
    if not (np.array_equal(aqc, aq) and np.array_equal(hqc, hq)):
        log('FINAL CLIP applied: arm max move %.4f rad, hand max move %.4f rad' % (np.max(np.abs(aqc - aq)), np.max(np.abs(hqc - hq))))
    aq, hq = aqc, hqc
    r = rig.probe(aq, hq); c = rig.cost(aq, hq, ARM_SEED)
    log('==== BEST cost=%.2f wall=%.1fs ====' % (c, time.time() - t0))
    log('arm_q=%s' % np.round(aq, 6).tolist())
    log('hand_q=%s' % np.round(hq, 6).tolist())
    log('cf=%s cube_bottom=%.4f bottom_vs_table=%+.1fmm over_table=%s wrist=%s' % (
        np.round(r['cf'], 5).tolist(), r['cube_bottom'], r['bottom_vs_table'] * 1e3, r['over_table'], np.round(r['wrist'], 4).tolist()))
    log('gaps mm thumb=%.2f index=%.2f middle=%.2f relz=%s palm=%.1fmm segmin=%.1fmm body_min=%s@%.1fmm table_d=%.1fmm span=%.1fmm' % (
        r['gap'][0] * 1e3, r['gap'][1] * 1e3, r['gap'][2] * 1e3, np.round([x[2] * 1e3 for x in r['rel']], 1).tolist(),
        r['palm'] * 1e3, r['segmin'] * 1e3, r['body_min'][0], r['body_min'][1] * 1e3, r['table_d'] * 1e3, r['span'] * 1e3))
    gm = [x * 1e3 for x in r['gap']]
    ok = (sum(-.9 <= x <= -0.02 for x in gm) >= 2) and r['palm'] * 1e3 > .3 and r['body_min'][1] * 1e3 > 5. and not (r['over_table'] and r['bottom_vs_table'] * 1e3 < 5.)
    log('DESIGN_OK=%s' % ok)
    hs = M / 'ws4h'
    preset = dict(cube_pos=[float(x) for x in r['cf']], arm_q=[float(x) for x in aq], weld=True, freeze_hand=True, skip_to_close=True,
                  note='W4h W1S seat2 edge=%gmm pads %s mm relz %s mm palm %.1fmm body %s@%.1fmm table_d %.1fmm span %.1fmm over_table %s bottom_vs_table %+.1fmm design_ok %s' % (
                      EDGE, np.round(np.array(r['gap']) * 1e3, 2).tolist(), np.round([x[2] * 1e3 for x in r['rel']], 1).tolist(), r['palm'] * 1e3,
                      r['body_min'][0], r['body_min'][1] * 1e3, r['table_d'] * 1e3, r['span'] * 1e3, r['over_table'], r['bottom_vs_table'] * 1e3, ok))
    (hs / 'presets' / ('preset_w1s_%g.json' % EDGE)).write_text(json.dumps(preset, indent=1) + '\n')
    grip = dict(grip_target_rad=[round(float(x), 6) for x in hq], note='W4h W1S seat2 envelope config %gmm' % EDGE)
    (hs / 'grips' / ('grip_w1s_%g.json' % EDGE)).write_text(json.dumps(grip, indent=1) + '\n')
    audit = dict(edge_mm=EDGE, cost=c, design_ok=ok, arm_q=aq.tolist(), hand_q=hq.tolist(), cf_m=r['cf'].tolist(),
                 pad_gap_mm=[float(x) * 1e3 for x in r['gap']], pad_relz_mm=[float(x[2]) * 1e3 for x in r['rel']],
                 palm_mm=r['palm'] * 1e3, seg_min_mm=r['segmin'] * 1e3, body_min=[r['body_min'][0], r['body_min'][1] * 1e3],
                 table_d_mm=r['table_d'] * 1e3, span_mm=r['span'] * 1e3, over_table=r['over_table'], bottom_vs_table_mm=r['bottom_vs_table'] * 1e3,
                 wrist_m=r['wrist'].tolist(), wall_s=time.time() - t0)
    (hs / ('seat2_audit_%g.json' % EDGE)).write_text(json.dumps(audit, indent=1) + '\n')
    log('WROTE preset/grip/audit for edge=%g' % EDGE)

if __name__ == '__main__':
    main()
