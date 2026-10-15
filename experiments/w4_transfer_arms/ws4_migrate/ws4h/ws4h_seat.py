#!/usr/bin/env python3
"""W4h W1S FK seat + envelope-config search (read-only wrt arm sources; writes only ws4h/).

Replicates the run() init pose of rep_ext_w1 exactly (pelvis 0,0,.788740; identity quat;
arm = neutral_body(DEFAULT_ANGLES, +0.2); hand OPEN), then for candidate hand configs:
  cf = contact_frame(opponent=middle) of the CLOSED-hand FK at that pose   [== the ALIGN
  equilibrium seat the route servos cf -> cube centre, so the cube preset must be cf]
and audits, with the cube moved to cf: pad sphere-box gaps, palm/wrist mesh distances
(the only non-pad colliders at level 0), distal-phalanx and whole-chain mesh distances,
span, cube bottom vs table top, wrist position + the whole-hand OPEN-hand clearance at the
same pose (for the record). Local coordinate descent minimises the marked cost; the best
configs are then written to ws4h/presets/preset_w1s_<edge>.json + ws4h/grips/grip_w1s_<edge>.json.

Usage: ws4h_seat.py EDGE [nseeds]
"""
import json, sys, time, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')

M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
AR = M / 'rep_ext_w1'
sys.path.insert(0, str(AR / 'rep'))
import sonic_grasp as sg
from grasp_geometry import contact_frame
from neutral_pose import neutral_body
import sonic_v11 as s
from source_physics_core import PADS, OPEN

EDGE = float(sys.argv[1]) if len(sys.argv) > 1 else 80.
NSEED = int(sys.argv[2]) if len(sys.argv) > 2 else 4
OPPONENT = 2  # frozen flags: --opponent middle
WRIST_BODIES = ('right_wrist_yaw_link',)
SEG_BODIES = ('right_hand_thumb_2_link', 'right_hand_index_1_link', 'right_hand_middle_1_link')

def log(*a):
    print(*a, flush=True)

def gap_box(rel, s, r=.010):
    dx = np.abs(rel) - s
    out = np.clip(dx, 0.0, None)
    if out.max() > 0:
        return float(np.linalg.norm(out) - r)
    return float(-(r + float(np.min(-dx))))

def band(x, lo, hi):
    return 0.0 if lo <= x <= hi else (lo - x if x < lo else x - hi) ** 2

def hinge(x):
    return 0.0 if x <= 0 else x * x

def build(edge):
    out = M / 'ws4h' / 'scratch' / ('seat_e%g' % edge)
    if out.exists():
        import shutil; shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    return sg.scene_and_cal(AR / 'rep', out, False, True, False, False, .24, float(edge), .285, -.138, 0., 0)[0]

class Rig:
    def __init__(self, edge):
        self.m = m = mujoco.MjModel.from_xml_path(str(build(edge)))
        self.d = d = mujoco.MjData(m)
        self.edge = edge; self.s = edge * .0005
        self.cube = m.geom('red_cube_geom').id
        self.pad_ids = [m.geom(n).id for n in PADS]
        self.hj = m.actuator_trnid[np.arange(36, 43), 0]; self.hq = m.jnt_qposadr[self.hj]
        self.aq = m.jnt_qposadr[m.actuator_trnid[:29, 0]]
        self.cq = int(m.jnt_qposadr[int(m.body('red_cube').jntadr[0])])
        self.table = m.geom('table_top').id
        self.table_top = float(d.geom_xpos[self.table, 2] + m.geom_size[self.table, 2]) if False else None
        def group0(bn):
            bid = m.body(bn).id
            return [g for g in range(m.ngeom) if int(m.geom_bodyid[g]) == bid and int(m.geom_group[g]) == 0 and (int(m.geom_contype[g]) or int(m.geom_conaffinity[g]))]
        self.wrist_geoms = []
        for bn in WRIST_BODIES:
            self.wrist_geoms += group0(bn)
        self.seg = {bn: group0(bn) for bn in SEG_BODIES}
        self.chain = {}
        for b in range(m.nbody):
            bn = m.body(b).name or ''
            if bn.startswith('right_hand_'):
                self.chain[bn] = group0(bn)
        # init pose, exactly as run():255
        self.neutral = neutral_body(m, s.DEFAULT_ANGLES, .2)
        d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[self.aq] = self.neutral; d.qpos[self.hq] = OPEN
        mujoco.mj_forward(m, d)
        self.table_top = float(d.geom_xpos[self.table, 2] + m.geom_size[self.table, 2])
        self.wrist = m.body('right_wrist_yaw_link').id
        self.init_wrist = d.xpos[self.wrist].copy()
        log('INIT_POSE wrist_m=%s table_top_m=%.4f cube_half_mm=%.1f' % (np.round(self.init_wrist, 4).tolist(), self.table_top, self.s * 1e3))
        log('JOINT_RANGES thumb_0 %s thumb_1 %s thumb_2 %s index_0 %s index_1 %s middle_0 %s middle_1 %s' % tuple(','.join('%.4f' % x for x in r) for r in m.jnt_range[self.hj].tolist()))

    def probe_qc(self, q):
        m, d = self.m, self.d
        q = np.clip(np.asarray(q, float), m.jnt_range[self.hj, 0] + 1e-9, m.jnt_range[self.hj, 1] - 1e-9)
        d.qpos[:] = 0
        d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[self.aq] = self.neutral; d.qpos[self.hq] = q
        mujoco.mj_forward(m, d)
        p = [d.geom_xpos[g].copy() for g in self.pad_ids]
        cf = contact_frame(m, d, d.xmat[m.body('red_cube').id].reshape(3, 3), opponent=OPPONENT).copy()
        d.qpos[self.cq:self.cq + 3] = cf; d.qpos[self.cq + 3:self.cq + 7] = [1., 0., 0., 0.]
        mujoco.mj_forward(m, d)
        r = dict(q=q, cf=cf, pads=p[:], rel=[p[i] - cf for i in range(3)])
        r['gap'] = [gap_box(r['rel'][i], self.s, float(m.geom_size[self.pad_ids[i], 0])) for i in range(3)]
        r['span'] = float(np.linalg.norm(p[2] - p[0]))
        r['palm'] = min(mujoco.mj_geomDistance(m, d, g, self.cube, .06, None) for g in self.wrist_geoms)
        r['palm_geoms'] = {m.geom(g).name or ('#%d' % g): float(mujoco.mj_geomDistance(m, d, g, self.cube, .06, None)) for g in self.wrist_geoms}
        r['seg'] = {bn: min(mujoco.mj_geomDistance(m, d, g, self.cube, .06, None) for g in self.seg[bn]) for bn in SEG_BODIES}
        r['segmin'] = min(r['seg'].values())
        allc = [(bn, float(mujoco.mj_geomDistance(m, d, g, self.cube, .06, None))) for bn in self.chain for g in self.chain[bn]]
        r['chainmin'] = min(x[1] for x in allc) if allc else 9.
        r['chainworst'] = min(allc, key=lambda x: x[1]) if allc else ('-', 9.)
        r['cube_bottom_vs_table_mm'] = float((cf[2] - self.s - self.table_top) * 1e3)
        r['wrist'] = d.xpos[self.wrist].copy()
        return r

    def cost(self, q, q0):
        try:
            r = self.probe_qc(q)
        except ValueError:
            return 1e9
        g = [x * 1e3 for x in r['gap']]
        rz = [x[2] * 1e3 for x in r['rel']]
        c = 0.
        c += 600. * band(g[0], -1.5, -0.3)
        c += 600. * band(g[1], -1.5, -0.3)
        c += 300. * band(g[2], -2.2, 0.5)
        c += 400. * hinge(0.3 - r['palm'] * 1e3)
        c += 200. * hinge(-1.2 - r['segmin'] * 1e3)
        c += 40. * hinge(-5.0 - r['chainmin'] * 1e3)
        c += 25. * hinge(20. - r['span'] * 1e3) + 25. * hinge(r['span'] * 1e3 - 170.)
        nband = int(sum(-1.5 <= x <= -0.3 for x in g))
        c -= 4000. * min(nband, 2)
        nlow = int(sum(x <= -30 for x in rz)); nup = int(sum(x >= 30 for x in rz))
        c -= 1500. * min(nlow, 1)
        c -= 600. * min(nup, 1)
        c += 5. * float(np.sum((np.asarray(q) - np.asarray(q0)) ** 2))
        return c

    def descend(self, q0):
        q = np.asarray(q0, float).copy()
        best = self.cost(q, q0)
        for step in (.10, .04, .015, .006, .0025):
            improved, guard = True, 0
            while improved and guard < 80:
                improved, guard = False, guard + 1
                for j in range(7):
                    for sgn in (1., -1.):
                        q2 = q.copy(); q2[j] += sgn * step
                        c = self.cost(q2, q0)
                        if c < best - 1e-9:
                            q, best, improved = np.clip(q2, self.m.jnt_range[self.hj, 0] + 1e-9, self.m.jnt_range[self.hj, 1] - 1e-9), c, True
        return q, best

def open_audit(rig, q, cf):
    """Record-only: OPEN hand at the same arm pose, cube at cf."""
    m, d = rig.m, rig.d
    d.qpos[:] = 0; d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]
    d.qpos[rig.aq] = rig.neutral; d.qpos[rig.hq] = OPEN
    d.qpos[rig.cq:rig.cq + 3] = cf; d.qpos[rig.cq + 3:rig.cq + 7] = [1., 0., 0., 0.]
    mujoco.mj_forward(m, d)
    allc = []
    for bn in rig.chain:
        for g in rig.chain[bn]:
            allc.append((bn, float(mujoco.mj_geomDistance(m, d, g, rig.cube, .08, None))))
    pads = [(PADS[i], gap_box(d.geom_xpos[rig.pad_ids[i]] - cf, rig.s, float(m.geom_size[rig.pad_ids[i], 0]))) for i in range(3)]
    return dict(open_chain_min_mm=min(x[1] for x in allc) * 1e3, open_worst=min(allc, key=lambda x: x[1]), open_pad_gaps_mm=[(n, round(g * 1e3, 2)) for n, g in pads], ncon_after_forward=int(d.ncon))

def main():
    t0 = time.time()
    rig = Rig(EDGE)
    # seeds: v5c family + the W4g candidates file top rows
    seeds = [
        [0.651, 0.223, -1.221, 1.833, 0.0, 1.794, 0.158],  # W4h survey X-best (cradle+side clamp)
        [0.857, 0.358, -0.071, 0.831, 1.298, 0.644, 1.327],  # W4h survey M1 (thumb top + index side)
        [-0.08, 0.347, -0.365, 1.296, 0.478, 1.132, 0.0],    # W4h survey M2
        [0.42, -0.2, -0.8, 1.7, 0.05, 1.7, 0.05],       # v5c top1 (hood reference)
        [0.4188, -0.0826, -0.9816, 1.648, 0.2547, 1.648, 0.2547],  # v5c top1 100
    ]
    candp = M / 'ws4g' / 'ws4g_env_candidates.json'
    if candp.exists():
        cands = json.loads(candp.read_text()).get(str(int(EDGE)), [])
        for row in cands[:6]:
            q = row.get('q') if isinstance(row, dict) else None
            if q: seeds.append([float(x) for x in q])
    rng = np.random.RandomState(4)
    jit = [np.clip(np.asarray(sd, float) + rng.normal(0, .18, 7), rig.m.jnt_range[rig.hj, 0] + 1e-6, rig.m.jnt_range[rig.hj, 1] - 1e-6).tolist() for sd in seeds[:2]]
    seeds = (seeds + jit)[:max(NSEED, 3)]
    best = None
    for k, q0 in enumerate(seeds):
        r0 = rig.probe_qc(q0); c0 = rig.cost(q0, q0)
        q, c = rig.descend(q0)
        r = rig.probe_qc(q)
        log('SEED%d c0=%.1f -> c=%.2f q=%s gaps=%s palm=%.2fmm segmin=%.2fmm span=%.1fmm' % (
            k, c0, c, np.round(q, 4).tolist(), np.round(np.array(r['gap']) * 1e3, 2).tolist(), r['palm'] * 1e3, r['segmin'] * 1e3, r['span'] * 1e3))
        if best is None or c < best[1]: best = (q, c, r)
    q, c, r = best
    log('==== BEST cost=%.3f (%.1fs) ====' % (c, time.time() - t0))
    log('q_rad=%s' % np.round(q, 6).tolist())
    log('cf_m=%s cube_bottom_vs_table=%.1fmm wrist_m=%s' % (np.round(r['cf'], 5).tolist(), r['cube_bottom_vs_table_mm'], np.round(r['wrist'], 4).tolist()))
    log('pad_gaps_mm thumb=%.2f index=%.2f middle=%.2f span=%.1fmm' % (r['gap'][0] * 1e3, r['gap'][1] * 1e3, r['gap'][2] * 1e3, r['span'] * 1e3))
    log('pad_relz_mm thumb=%.1f index=%.1f middle=%.1f' % tuple(x[2] * 1e3 for x in r['rel']))
    log('palm_mm %s' % {k: round(v * 1e3, 2) for k, v in r['palm_geoms'].items()})
    log('seg_mm %s chain_worst=%s@%.2fmm' % ({k: round(v * 1e3, 2) for k, v in r['seg'].items()}, r['chainworst'][0], r['chainworst'][1] * 1e3))
    oa = open_audit(rig, q, r['cf'])
    log('OPEN_hand_audit %s' % json.dumps(oa))
    # write artifacts
    hs = M / 'ws4h'
    preset = dict(cube_pos=[float(x) for x in r['cf']], weld=True, freeze_hand=True, skip_to_close=True,
                  note='W4h W1S seat for edge=%gmm: contact_frame(middle) of q below at the rep_ext_w1 init pose; pads %s mm; palm min %.2fmm; segmin %.2fmm; span %.1fmm' % (
                      EDGE, np.round(np.array(r['gap']) * 1e3, 2).tolist(), r['palm'] * 1e3, r['segmin'] * 1e3, r['span'] * 1e3))
    (hs / 'presets' / ('preset_w1s_%g.json' % EDGE)).write_text(json.dumps(preset, indent=1) + '\n')
    grip = dict(grip_target_rad=[round(float(x), 6) for x in q],
                note='W4h W1S envelope config for %gmm (local descent from v5c); audit %s' % (EDGE, json.dumps(dict(pad_gap_mm=[round(float(x) * 1e3, 2) for x in r['gap']], palm_min_mm=round(r['palm'] * 1e3, 2), seg_min_mm=round(r['segmin'] * 1e3, 2), span_mm=round(r['span'] * 1e3, 1)))))
    (hs / 'grips' / ('grip_w1s_%g.json' % EDGE)).write_text(json.dumps(grip, indent=1) + '\n')
    audit = dict(edge_mm=EDGE, q_rad=[float(x) for x in q], cost=c, cf_m=[float(x) for x in r['cf']],
                 pad_gap_mm=[float(x) * 1e3 for x in r['gap']], span_mm=r['span'] * 1e3,
                 palm_mm={k: v * 1e3 for k, v in r['palm_geoms'].items()}, seg_mm={k: v * 1e3 for k, v in r['seg'].items()},
                 chain_worst=[r['chainworst'][0], r['chainworst'][1] * 1e3], cube_bottom_vs_table_mm=r['cube_bottom_vs_table_mm'],
                 wrist_m=r['wrist'].tolist(), init_pose_wrist_m=rig.init_wrist.tolist(), table_top_m=rig.table_top, open_hand=oa, wall_s=time.time() - t0)
    (hs / ('seat_audit_%g.json' % EDGE)).write_text(json.dumps(audit, indent=1) + '\n')
    log('WROTE %s' % (hs / 'presets' / ('preset_w1s_%g.json' % EDGE)))

if __name__ == '__main__':
    main()
