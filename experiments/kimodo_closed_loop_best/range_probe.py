#!/usr/bin/env python3
"""Compare clip arm-joint values against the model's declared joint ranges.

Usage: range_probe.py <scene.xml> <clip.npz> [<clip.npz> ...]
"""
import sys
from pathlib import Path
import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion_input as mi  # noqa: E402

SCENE = sys.argv[1]
m = mujoco.MjModel.from_xml_path(SCENE)

# hinge joints in model order (skip the free joint)
hinge = [j for j in range(m.njnt) if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE]
print("nq=%d nv=%d njnt=%d hinges=%d" % (m.nq, m.nv, m.njnt, len(hinge)))
print("%4s %-34s %9s %9s" % ("idx", "joint", "lo", "hi"))
for i, j in enumerate(hinge):
    nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j)
    print("%4d %-34s %9.4f %9.4f" % (i, nm, m.jnt_range[j, 0], m.jnt_range[j, 1]))

lo = np.array([m.jnt_range[j, 0] for j in hinge])
hi = np.array([m.jnt_range[j, 1] for j in hinge])

for spec in sys.argv[2:]:
    p = Path(spec)
    mm = mi.ArdyMotion(p)
    q = mm.qpos[:, 7:]           # (T, 29) body joints
    print("\n== %s  T=%d" % (p.stem, len(q)))
    for i in range(15, 29):
        v = q[:, i]
        nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, hinge[i])
        bad = int(((v < lo[i] - 1e-9) | (v > hi[i] + 1e-9)).sum())
        print("  %2d %-30s clip[%7.3f,%7.3f]  range[%7.3f,%7.3f]  out=%d/%d"
              % (i, nm, v.min(), v.max(), lo[i], hi[i], bad, len(v)))
