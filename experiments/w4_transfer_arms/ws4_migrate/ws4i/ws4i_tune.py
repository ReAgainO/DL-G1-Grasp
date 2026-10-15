#!/usr/bin/env python3
"""W4i tune: refine 50mm-class candidates from the (single) corrected search into a
BALANCED OPPOSED PINCH: >=3 pad contacts, net pad normal ~ 0 (opposed squeeze, no shove),
CoM inside the contact hull (xy), shallow press, and a REAL body clearance budget
(>=60mm - the seat4-best seat had 19mm and a hip/thigh crushed the cube at runtime).
Usage: ws4i_tune.py EDGE
"""
import json, sys, time, warnings
import numpy as np
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
sys.path.insert(0, str(M / 'ws4i'))
from ws4i_seat4 import Rig3, ARM_SEED, HAND_SEED_Q, band, hinge

EDGE = float(sys.argv[1]) if len(sys.argv) > 1 else 50.
def log(*a): print(*a, flush=True)

def hull_margin(pts, com):
    if len(pts) >= 3:
        ctr = pts.mean(axis=0)
        ang = np.arctan2((pts - ctr)[:, 1], (pts - ctr)[:, 0])
        pts = pts[np.argsort(ang)]
        m = 1e9
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            e = b - a; L = np.linalg.norm(e)
            if L < 1e-9: continue
            nrm = np.array([-e[1], e[0]]) / L
            dd = float(nrm @ (com - a))
            if float(nrm @ (ctr - a)) < 0: dd = -dd
            m = min(m, dd)
        return m
    if len(pts) == 2:
        a, b = pts; e = b - a; L = np.linalg.norm(e)
        if L < 1e-9: return 0.
        t = float(np.clip(np.dot(com - a, e) / (L * L), 0, 1))
        return -float(np.linalg.norm(com - (a + t * e)))
    return -1e9

def cost(rig, arm, hand, delta):
    try:
        r = rig.probe(arm, hand, delta)
    except Exception:
        return 1e9, None
    g = [x * 1e3 for x in r['gap']]
    c = 0.
    for x in g:
        c += 800. * band(x, -0.7, -0.3)
        if x < -1.0: c += 800. * (x + 1.0) ** 2
    c += 800. * hinge(60.0 - r['body_min'][1] * 1e3)
    c += 500. * hinge(20.0 - r['palm'] * 1e3)
    c += 500. * hinge(20.0 - r['table_d'] * 1e3)
    nc = len(r['pad_contacts'])
    if nc < 3: c += 6000. * (3 - nc)
    if nc:
        N = np.sum([pc['n'] for pc in r['pad_contacts']], axis=0)
        c += 3000. * float(N @ N)
        pts = np.array([pc['pos'][:2] for pc in r['pad_contacts']])
        mm = hull_margin(pts, r['cpos'][:2]) * 1e3
        c += 200. * max(0., 6. - mm) ** 2
    c += 5. * float(np.sum((np.asarray(arm) - np.asarray(ARM_SEED)) ** 2)) + 5. * float(np.sum(np.asarray(delta) ** 2 * 1e4))
    return c, r

def descend(rig, arm, hand, delta):
    arm = np.asarray(arm, float).copy(); hand = np.asarray(hand, float).copy(); delta = np.asarray(delta, float).copy()
    best, _ = cost(rig, arm, hand, delta)
    rounds = [('h', (.10, .04, .015, .006)), ('d', (.04, .015, .006, .002)), ('a', (.10, .04, .015)), ('h', (.02, .008, .003)), ('d', (.008, .003)), ('a', (.012, .005))]
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
                        c, _ = cost(rig, a2, h2, d2)
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
    cands = []
    ap = M / 'ws4i' / ('audit_seat4_%g.json' % EDGE)
    if ap.exists():
        a = json.loads(ap.read_text())
        cands.append((np.array(a['arm_q']), np.array(a['hand_q']), np.array(a['delta_mm']) * 1e-3))
    for hq in HAND_SEED_Q:
        cands.append((np.array(ARM_SEED), np.array(hq), np.zeros(3)))
    rng = np.random.RandomState(77)
    for i in range(6):
        cands.append((np.clip(np.array(ARM_SEED) + rng.normal(0, .4, 7), lo_a, hi_a),
                      np.clip(np.array(HAND_SEED_Q[i % len(HAND_SEED_Q)]) + rng.normal(0, .4, 7), lo_h, hi_h),
                      rng.uniform(-.03, .03, 3)))
    res = []
    for k, (a0, h0, d0) in enumerate(cands):
        a, h, d, c = descend(rig, a0, h0, d0)
        cc, r = cost(rig, a, h, d)
        nsum = np.sum([pc['n'] for pc in r['pad_contacts']], axis=0) if r['pad_contacts'] else np.zeros(3)
        log('SEED%d c=%.1f arm=%s hand=%s d_mm=%s gaps=%s nc=%d sumN=%.2f palm=%.1f body=%s@%.1f tab=%.1f' % (
            k, cc, np.round(a, 3).tolist(), np.round(h, 3).tolist(), np.round(d * 1e3, 1).tolist(),
            np.round(np.array(r['gap']) * 1e3, 2).tolist(), len(r['pad_contacts']), float(np.linalg.norm(nsum)),
            r['palm'] * 1e3, r['body_min'][0], r['body_min'][1] * 1e3, r['table_d'] * 1e3))
        res.append((cc, a, h, d, r))
    res.sort(key=lambda x: x[0])
    for rank, (cc, a, h, d, r) in enumerate(res[:3]):
        log('CAND%d cost=%.1f cube_pos=%s' % (rank, cc, np.round(r['cpos'], 5).tolist()))
    cc, a, h, d, r = res[0]
    a = np.clip(a, lo_a, hi_a); h = np.clip(h, lo_h, hi_h)
    _, r = cost(rig, a, h, d)
    log('==== BEST cost=%.2f wall=%.1fs ====' % (cc, time.time() - t0))
    log('arm_q=%s' % np.round(a, 6).tolist()); log('hand_q=%s' % np.round(h, 6).tolist())
    log('cf=%s delta_mm=%s cube_pos=%s' % (np.round(r['cf'], 5).tolist(), np.round(d * 1e3, 2).tolist(), np.round(r['cpos'], 5).tolist()))
    log('gaps_mm=%s palm=%.1fmm body=%s@%.1fmm table_d=%.1fmm span=%.1fmm' % (
        np.round(np.array(r['gap']) * 1e3, 2).tolist(), r['palm'] * 1e3, r['body_min'][0], r['body_min'][1] * 1e3, r['table_d'] * 1e3, r['span'] * 1e3))
    nsum = np.zeros(3)
    for c_ in r['pad_contacts']:
        nsum = nsum + c_['n']
        log('   contact %s n=%s n_z=%.2f pos=%s' % (c_['body'], np.round(c_['n'], 2).tolist(), c_['n'][2], np.round(c_['pos'], 4).tolist()))
    log('sum_pad_normal=%s |sum|=%.2f' % (np.round(nsum, 2).tolist(), float(np.linalg.norm(nsum))))
    hs = M / 'ws4i'
    preset = dict(cube_pos=[float(x) for x in r['cpos']], arm_q=[float(x) for x in a], weld=True, freeze_hand=True,
                  skip_to_close=True, settle_s=0.5, weld_release='LIFT',
                  design_gaps_mm=[round(float(x) * 1e3, 3) for x in r['gap']],
                  note='W4i tune edge=%gmm balanced opposed pinch: cf+delta %s mm; pads %s mm; abs_sumN=%.2f; palm %.1f; body %s@%.1f; tab %.1f' % (
                      EDGE, np.round(d * 1e3, 2).tolist(), np.round(np.array(r['gap']) * 1e3, 2).tolist(), float(np.linalg.norm(nsum)),
                      r['palm'] * 1e3, r['body_min'][0], r['body_min'][1] * 1e3, r['table_d'] * 1e3))
    (hs / 'presets' / ('preset_w1s_%g_pinch.json' % EDGE)).write_text(json.dumps(preset, indent=1) + '\n')
    (hs / 'grips' / ('grip_w1s_%g_pinch.json' % EDGE)).write_text(json.dumps(dict(grip_target_rad=[round(float(x), 6) for x in h]), indent=1) + '\n')
    audit = dict(edge_mm=EDGE, cost=cc, arm_q=a.tolist(), hand_q=h.tolist(), cf_m=r['cf'].tolist(), delta_mm=(d * 1e3).tolist(),
                 cube_pos_m=r['cpos'].tolist(), pad_gap_mm=[float(x) * 1e3 for x in r['gap']], palm_mm=r['palm'] * 1e3,
                 body_min=[r['body_min'][0], r['body_min'][1] * 1e3], table_d_mm=r['table_d'] * 1e3, span_mm=r['span'] * 1e3,
                 pad_contacts=[dict(body=c_['body'], n=[float(x) for x in c_['n']], pos=[float(x) for x in c_['pos']], dist_mm=float(c_['dist']) * 1e3) for c_ in r['pad_contacts']],
                 sum_pad_normal=[float(x) for x in nsum],
                 top3=[dict(cost=float(x[0]), arm_q=x[1].tolist(), hand_q=x[2].tolist(), delta_mm=(x[3] * 1e3).tolist(), cube_pos_m=x[4]['cpos'].tolist()) for x in res[:3]],
                 wall_s=time.time() - t0)
    (hs / ('audit_pinch_%g.json' % EDGE)).write_text(json.dumps(audit, indent=1) + '\n')
    log('WROTE preset/grip/audit (tune) for edge=%g' % EDGE)

if __name__ == '__main__':
    main()
