"""W5b FK probe (read-only): measure right-hand Dex3 fingertip opening geometry.

Loads the group's g1_29dof_with_hand.xml (read-only) and computes distances
between fingertip sphere centers (thumb vs index, thumb vs middle, index vs middle)
for key configurations and for a grid search over full joint ranges.
"""
import mujoco
import numpy as np
import itertools

XML = '/home/group4/group4_dasc7606c/repos/sonic-bridge/g1/g1_29dof_with_hand.xml'
m = mujoco.MjModel.from_xml_path(XML)
d = mujoco.MjData(m)

JN = ['right_hand_thumb_0_joint', 'right_hand_thumb_1_joint', 'right_hand_thumb_2_joint',
      'right_hand_index_0_joint', 'right_hand_index_1_joint',
      'right_hand_middle_0_joint', 'right_hand_middle_1_joint']
jid = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n) for n in JN}
qadr = {n: int(m.jnt_qposadr[jid[n]]) for n in JN}
# ranges straight from the model
RANGES = {n: m.jnt_range[jid[n]].copy() for n in JN}

TIP = {}
for tag, body, off in [('thumb', 'right_hand_thumb_2_link', [0.0, 0.054, 0.0]),
                       ('index', 'right_hand_index_1_link', [0.054, 0.0, 0.0]),
                       ('middle', 'right_hand_middle_1_link', [0.054, 0.0, 0.0])]:
    TIP[tag] = (mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, body), np.array(off))
# fingertip sphere radius (from XML geoms)
R_TIP = 0.010


def setq(vals):
    for n, v in zip(JN, vals):
        d.qpos[qadr[n]] = v
    mujoco.mj_forward(m, d)


def tips():
    out = {}
    for tag, (bid, off) in TIP.items():
        out[tag] = d.xpos[bid] + d.xmat[bid].reshape(3, 3) @ off
    return out


def metrics(vals):
    setq(vals)
    t = tips()
    thumb_index = float(np.linalg.norm(t['thumb'] - t['index']))
    thumb_middle = float(np.linalg.norm(t['thumb'] - t['middle']))
    index_middle = float(np.linalg.norm(t['index'] - t['middle']))
    span = min(thumb_index, thumb_middle)  # pinch span between thumb and either opposing finger
    return span, thumb_index, thumb_middle, index_middle


OPEN = [0.0, -0.70, -2.00, 1.40, 0.08, 1.40, 0.08]
CLOSED = [0.0, -0.60, -0.425, 1.40, 0.08, 1.40, 0.08]

print('== key configs (tip center distances; free gap = dist - 2*10mm) ==')
for name, cfg in [('OPEN', OPEN), ('CLOSED', CLOSED)]:
    s, ti, tm, im = metrics(cfg)
    print(f'{name}: span(min)={s*1e3:.1f}mm  thumb-index={ti*1e3:.1f}mm  '
          f'thumb-middle={tm*1e3:.1f}mm  index-middle={im*1e3:.1f}mm  '
          f'freegap(span-20mm)={(s-2*R_TIP)*1e3:.1f}mm')

print()
print('== ranges from model ==')
for n in JN:
    print(f'{n}: [{RANGES[n][0]:.6f}, {RANGES[n][1]:.6f}]')

# --- Search 1: thumb swept over its full ranges, index/middle FIXED at controller
# value [1.40, 0.08] (this reproduces the group's controller constraint) ---
def coarse_range(n, k=6):
    lo, hi = RANGES[n]
    return np.linspace(lo, hi, k)

best_fixed = None
for v0 in coarse_range(JN[0]):
    for v1 in coarse_range(JN[1]):
        for v2 in coarse_range(JN[2]):
            cfg = [v0, v1, v2, 1.40, 0.08, 1.40, 0.08]
            s, ti, tm, im = metrics(cfg)
            if best_fixed is None or s > best_fixed[0]:
                best_fixed = (s, ti, tm, cfg)
print()
print('== Search1: thumb over full range, index/middle PINNED at [1.40, 0.08] ==')
print(f'max span={best_fixed[0]*1e3:.1f}mm  thumb-index={best_fixed[1]*1e3:.1f}mm '
      f'thumb-middle={best_fixed[2]*1e3:.1f}mm  cfg={[round(v,4) for v in best_fixed[3]]}')

# --- Search 2: ALL 7 joints over their ranges (coarse then refine) ---
def grid_all(k):
    grids = [np.linspace(RANGES[n][0], RANGES[n][1], k) for n in JN]
    best = None
    for vals in itertools.product(*grids):
        s, ti, tm, im = metrics(list(vals))
        if best is None or s > best[0]:
            best = (s, ti, tm, list(vals))
    return best

best = grid_all(4)
print()
print('== Search2: all 7 joints over ranges, coarse k=4 ==')
print(f'max span={best[0]*1e3:.1f}mm cfg={[round(v,4) for v in best[3]]}')

# refine around best with local grid
lo = [max(RANGES[n][0], best[3][i] - (RANGES[n][1] - RANGES[n][0]) / 3) for i, n in enumerate(JN)]
hi = [min(RANGES[n][1], best[3][i] + (RANGES[n][1] - RANGES[n][0]) / 3) for i, n in enumerate(JN)]
grids = [np.linspace(lo[i], hi[i], 5) for i in range(7)]
best2 = None
for vals in itertools.product(*grids):
    s, ti, tm, im = metrics(list(vals))
    if best2 is None or s > best2[0]:
        best2 = (s, ti, tm, list(vals))
print('== Search2b: refined ==')
print(f'max span={best2[0]*1e3:.1f}mm  thumb-index={best2[1]*1e3:.1f}mm cfg={[round(v,4) for v in best2[3]]}')

# --- Search 3: max possible thumb-index distance with index at its most spread config
# index_0 range [-0.191986, 1.8326]; find "flattest" extension of index finger ---
print()
print('== Search3: max thumb-index / thumb-middle over full grid, report flat-index candidates ==')
best3 = None
for v0 in np.linspace(-1.0472, 1.0472, 5):
    for v1 in np.linspace(-1.0472, 0.724312, 5):
        for v2 in np.linspace(-2.0944, 0.0, 5):
            for vi0 in np.linspace(-0.191986, 1.8326, 6):
                for vi1 in np.linspace(0.0, 2.0944, 6):
                    cfg = [v0, v1, v2, vi0, vi1, vi0, vi1]
                    s, ti, tm, im = metrics(cfg)
                    if best3 is None or ti > best3[0]:
                        best3 = (ti, tm, s, cfg)
print(f'max thumb-index={best3[0]*1e3:.1f}mm thumb-middle={best3[1]*1e3:.1f}mm '
      f'span={best3[2]*1e3:.1f}mm cfg={[round(v,4) for v in best3[3]]}')

# --- Required center distances to straddle cubes with tip spheres (r=10mm) ---
print()
print('== straddle requirement (sphere center distance >= cube + 2*10mm) ==')
for s_mm in (16, 20, 25, 35):
    print(f'cube {s_mm}mm -> need center dist >= {s_mm + 20}mm; '
          f'OPEN gives {(min(metrics(OPEN)[1], metrics(OPEN)[2]))*1e3:.1f}mm')
