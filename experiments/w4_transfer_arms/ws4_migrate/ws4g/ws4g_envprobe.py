#!/usr/bin/env python3
"""W4g ENV collision/fit audit (read-only on rep_ext_env sources).

For each cube size and candidate 7-joint envelope config:
 1. builds scene.xml through the ARM's own modified scene_and_cal at
    --envelope-collision level L (scratch dir ws4g/scratch/L<L>_e<edge>_<x>_<y>),
    reloads it and prints the loaded contype/conaffinity of every
    right_hand_*/right_wrist_yaw_link geom => "enablement took effect" evidence;
 2. FK: sets the baseline b25_12_04 CLOSE-entry pose (wrist orientation fixed by the
    pipeline) plus the candidate hand joints, computes pads/n/span/contact-frame cf,
    moves the red_cube body to cf (what the runtime alignment does), then reports for
    every hand-chain geom the mj_geomDistance to the cube (reachability) and, via
    mj_collision, the real contact pairs + penetration at that pose, per level.

Candidates: JSON list [{"edge":80,"q":[...7...],"note":"..."}] (argv[1]); optional.
Output: ws4g_envprobe.out (stdout redirect by caller).
"""
import json, sys, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')

M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
AR = M / 'rep_ext_env'
B25 = M / 'rep_base/rep/out/b25_12_04'
sys.path.insert(0, str(AR / 'rep'))
import sonic_grasp as sg

PADS = ('right_thumb_fingertip', 'right_index_fingertip', 'right_middle_fingertip')
DISTMAX = 0.05

def log(*a):
    print(*a, flush=True)

def build(level, edge_mm, cx, cy):
    out = M / 'ws4g' / 'scratch' / ('L%d_e%g_%g_%g' % (level, edge_mm, cx, cy))
    if out.exists():__import__('shutil').rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    scn = sg.scene_and_cal(AR / 'rep', out, False, True, False, False, .24, float(edge_mm), float(cx), float(cy), 0., level)
    return scn[0]

def load(level, edge_mm, cx, cy):
    scn = build(level, edge_mm, cx, cy)
    m = mujoco.MjModel.from_xml_path(str(scn))
    d = mujoco.MjData(m)
    return m, d

def chain_ids(m):
    return [g for g in range(m.ngeom) if m.body(int(m.geom_bodyid[g])).name.startswith('right_hand_') or m.body(int(m.geom_bodyid[g])).name == 'right_wrist_yaw_link']

def label(m, g):
    nm = m.geom(g).name
    return '%s/%s#%d' % (m.body(int(m.geom_bodyid[g])).name, nm if nm else '-', g)

def baseline_pose(m, d):
    tr = np.load(B25 / 'trajectory.npz', allow_pickle=True)
    ph = [str(p) for p in tr['phase']]
    i0 = ph.index('CLOSE')
    q = tr['qpos'][i0].copy()
    d.qpos[:] = q
    mujoco.mj_forward(m, d)
    return q

def gap_box(rel, s, r=.010):
    dx = np.abs(rel) - s
    out = np.clip(dx, 0.0, None)
    if out.max() > 0:
        return float(np.linalg.norm(out) - r)
    return float(-(r + float(np.min(-dx))))

def audit_pose(m, d, qh, s, cube_gid, hand_joints):
    hj = m.actuator_trnid[np.arange(36, 43), 0]
    hq = m.jnt_qposadr[hj]
    pad_ids = [m.geom(n).id for n in PADS]
    d.qpos[hq] = np.clip(np.asarray(qh), m.jnt_range[hj, 0] + 1e-9, m.jnt_range[hj, 1] - 1e-9)
    mujoco.mj_forward(m, d)
    p = [d.geom_xpos[g].copy() for g in pad_ids]
    v = p[2] - p[0]
    L = float(np.linalg.norm(v))
    n = v / L
    cf = p[2] - n * (s * float(np.abs(n).sum()) + .010 - .0005)
    jid = int(m.body('red_cube').jntadr[0])
    qa = int(m.jnt_qposadr[jid])
    d.qpos[qa:qa + 3] = cf
    d.qpos[qa + 3:qa + 7] = [1., 0., 0., 0.]
    mujoco.mj_forward(m, d)
    return dict(cf=cf, n=n, span=L, pads=[d.geom_xpos[g].copy() for g in pad_ids])

def pose_report(m, d, qa_info, cube_gid):
    s = float(m.geom_size[cube_gid, 0])
    cube_c = d.xpos[m.body('red_cube').id].copy()
    rows = []
    for g in chain_ids(m):
        dist = mujoco.mj_geomDistance(m, d, g, cube_gid, DISTMAX, None)
        rows.append((g, dist))
    rows.sort(key=lambda x: x[1])
    out = []
    for g, dist in rows:
        if dist < DISTMAX:
            out.append('%s d=%+.1fmm' % (label(m, g), dist * 1e3))
    return out

def contacts_of(m, d, cube_gid):
    mujoco.mj_collision(m, d)
    chain = set(chain_ids(m))
    pairs = []
    for i in range(d.ncon):
        c = d.contact[i]
        g1, g2 = int(c.geom1), int(c.geom2)
        if g1 == cube_gid and g2 in chain:
            pairs.append('%s<->cube dist=%+.2fmm' % (label(m, g2), c.dist * 1e3))
        elif g2 == cube_gid and g1 in chain:
            pairs.append('%s<->cube dist=%+.2fmm' % (label(m, g1), c.dist * 1e3))
    return pairs

def main():
    cands = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else []
    mcache = {}

    def get(level, edge, cx=None, cy=-.138):
        cx = .24 + edge * .0005 + .004 if cx is None else cx
        k = (level, float(edge))
        if k not in mcache:
            mcache[k] = load(level, float(edge), cx, cy)
        return mcache[k]

    log('== W4g ENV probe: levels / masks (80mm scene build) ==')
    for level in (0, 1, 2):
        m, d = get(level, 80)
        on = []
        for g in chain_ids(m):
            if int(m.geom_contype[g]) or int(m.geom_conaffinity[g]):
                on.append('%s c=%d a=%d' % (label(m, g), int(m.geom_contype[g]), int(m.geom_conaffinity[g])))
        log('level=%d chain_geoms_with_collision=%d:' % (level, len(on)))
        for x in on:
            log('   ', x)
    log()

    log('== candidate audits (pose: b25 CLOSE-entry wrist + candidate hand joints; cube moved to cf) ==')
    for cd in cands:
        edge = cd['edge']; qh = cd['q']; s = edge * .0005
        note = cd.get('note', '')
        cube_gid = get(0, edge)[0].geom('red_cube_geom').id
        log('--- edge=%d q=%s %s' % (edge, [round(float(x), 4) for x in qh], note))
        for lv in (0, 1, 2):
            mm, dd = get(lv, edge)
            baseline_pose(mm, dd)
            info = audit_pose(mm, dd, qh, s, cube_gid, None)
            if lv == 0:
                log('    span=%.1fmm n=%s cf=%s' % (info['span'] * 1e3, np.round(info['n'], 3).tolist(), np.round(info['cf'] * 1e3, 1).tolist()))
                for i, k in enumerate(['thumb', 'index', 'middle']):
                    rel = (info['pads'][i] - info['cf'])
                    log('    %-6s rel_cf=%s mm gap=%+.2fmm' % (k, np.round(rel * 1e3, 1).tolist(), gap_box(rel, s) * 1e3))
            near = pose_report(mm, dd, None, cube_gid)
            pairs = contacts_of(mm, dd, cube_gid)
            log('    [level %d] near(<50mm): %s' % (lv, '; '.join(near) if near else 'none'))
            log('    [level %d] cube contacts: %s' % (lv, '; '.join(pairs) if pairs else 'none'))
    log('DONE')

if __name__ == '__main__':
    main()
