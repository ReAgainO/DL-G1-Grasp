#!/usr/bin/env python3
"""Correct-layout probe for candidate reach clips.

Key facts established with map_probe.py on the harness scene:
  qpos: freejoint 0-6 | left leg 7-12 | right leg 13-18 | waist 19-21
        left arm 22-28 | left hand 29-35 | right arm 36-42 | right hand 43-49
        cube 50-56
  body(non-hand) joints, in G1Skeleton34 / ArdyMotion order, live at
  adrs = [7..28, 36..42]   ->  index 22..28 == RIGHT ARM == adrs 36..42

Usage: clip_probe.py <scene.xml> <clip.npz> [<clip.npz> ...]
"""
import sys
from pathlib import Path
import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion_input as mi  # noqa: E402

SCENE = sys.argv[1]
CUBE = np.array([0.267, -0.118, 0.7745])
ANCHOR = np.array([0.0, 0.0, 0.7887])

m = mujoco.MjModel.from_xml_path(SCENE)
d = mujoco.MjData(m)
mujoco.mj_forward(m, d)
tid = m.geom("table_top").id
table_top_z = float(d.geom_xpos[tid, 2] + m.geom_size[tid, 2])
clearance_z = max(0.90, table_top_z + 0.14)
WB = int(m.body("right_wrist_yaw_link").id)

hinge = [j for j in range(m.njnt) if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE]
badr = [int(m.jnt_qposadr[j]) for j in hinge
        if "hand" not in (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) or "")]
rlo = np.array([m.jnt_range[j, 0] for j in hinge])
rhi = np.array([m.jnt_range[j, 1] for j in hinge])
# ranges for the 29 body joints, same order as badr
bidx = [i for i, j in enumerate(hinge)
        if "hand" not in (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) or "")]
blo = rlo[bidx]
bhi = rhi[bidx]
print("table_top_z=%.4f clearance_z=%.4f  body-adrs=%s" % (table_top_z, clearance_z, badr))


def fk(jrow):
    d.qpos[:] = 0.0
    d.qpos[:3] = ANCHOR
    d.qpos[3:7] = [1, 0, 0, 0]
    for adr, val in zip(badr, jrow):
        d.qpos[adr] = val
    mujoco.mj_forward(m, d)
    return d.xpos[WB].copy()


RARM = list(range(22, 29))
for spec in sys.argv[2:]:
    p = Path(spec)
    mm = mi.ArdyMotion(p)
    T = len(mm.qpos)
    jr = mm.qpos[:, 7:]                       # (T,29) body joints
    w = np.asarray([fk(jr[f]) for f in range(T)])
    dist = np.linalg.norm(w - CUBE, axis=1)
    print("\n== %-16s T=%d  clip=%.2fs" % (p.stem, T, mm.times[-1]))
    print("   wrist_z %.3f..%.3f   min|cube-wrist| %.1f mm @tau=%.2f"
          % (w[:, 2].min(), w[:, 2].max(), dist.min() * 1000, mm.times[int(np.argmin(dist))]))
    print("   frames with wrist_z>=%.2f : %d/%d" % (clearance_z, int((w[:, 2] >= clearance_z).sum()), T))
    a = int(0.4 / mm.times[-1] * T); b = int(2.6 / mm.times[-1] * T)
    print("   APPROACH tau .4-2.6 : wrist_z %.3f..%.3f  ok=%s"
          % (w[a:b + 1, 2].min(), w[a:b + 1, 2].max(), bool((w[a:b + 1, 2] >= clearance_z).any())))
    print("   %-34s %8s %8s %8s %6s" % ("right-arm joint", "clip_lo", "clip_hi", "range_hi", "out"))
    for k, i in enumerate(RARM):
        v = jr[:, i]
        bad = int(((v < blo[i] - 1e-9) | (v > bhi[i] + 1e-9)).sum())
        nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, hinge[bidx[i]])
        print("   %-34s %8.3f %8.3f %8.3f %3d/%d "
              % (nm, v.min(), v.max(), bhi[i], bad, T))
        print("   %-34s lo=%.3f hi=%.3f" % ("", blo[i], bhi[i]))
