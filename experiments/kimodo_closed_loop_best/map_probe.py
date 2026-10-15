#!/usr/bin/env python3
"""Resolve the true joint -> qpos-address layout and how a 29-value ArdyMotion
body-joint row maps onto it.  Decisive, no assumptions.

Usage: map_probe.py <scene.xml> [<clip.npz>]
"""
import sys
from pathlib import Path
import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion_input as mi  # noqa: E402

SCENE = sys.argv[1]
m = mujoco.MjModel.from_xml_path(SCENE)
print("nq=%d nv=%d njnt=%d" % (m.nq, m.nv, m.njnt))

rows = []
for j in range(m.njnt):
    nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) or "?"
    bd = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, m.jnt_bodyid[j]) or "?"
    rows.append((j, nm, m.jnt_type[j], int(m.jnt_qposadr[j]), int(m.jnt_dofadr[j]), bd))
for r in rows:
    print("jnt %2d adr %3d dof %3d type %d parent=%-24s %s"
          % (r[0], r[3], r[4], r[2], r[5], r[1]))

hinge = [r for r in rows if r[2] == mujoco.mjtJoint.mjJNT_HINGE]
body = [r for r in hinge if "hand" not in r[1]]
print("\nhinges=%d body(non-hand)=%d" % (len(hinge), len(body)))
print("body adrs :", [r[3] for r in body])
print("hand adrs :", [r[3] for r in hinge if "hand" in r[1]])
print("all hinge adrs :", [r[3] for r in hinge])

WB = int(m.body("right_wrist_yaw_link").id)
ANCHOR = np.array([0.0, 0.0, 0.7887])


def wrist_z(assign):
    d = mujoco.MjData(m)
    d.qpos[:] = 0.0
    d.qpos[:3] = ANCHOR
    d.qpos[3:7] = [1, 0, 0, 0]
    for adr, val in assign:
        d.qpos[adr] = val
    mujoco.mj_forward(m, d)
    return float(d.xpos[WB, 2])


# sensitivity: which qpos addresses actually move the RIGHT wrist?
print("\n-- single-joint +0.4 rad sensitivity of right wrist z --")
base = wrist_z([])
sens = []
for r in hinge:
    z = wrist_z([(r[3], 0.4)])
    if abs(z - base) > 1e-9:
        sens.append((r[0], r[1], r[3], z - base))
for s in sorted(sens, key=lambda x: -abs(x[3]))[:20]:
    print("   jnt %2d adr %3d dZ=%+.4f  %s" % (s[0], s[2], s[3], s[1]))
print("   total joints moving right wrist: %d" % len(sens))

if len(sys.argv) > 2:
    mm = mi.ArdyMotion(sys.argv[2])
    q = mm.qpos[:, 7:]                      # (T,29) body joints, G1Skeleton34 order
    badr = [r[3] for r in body]
    print("\n-- %s: two candidate mappings --" % Path(sys.argv[2]).stem)
    for tag, fn in [("A qpos[7:36]=jrow", lambda j: list(zip(range(7, 36), j))),
                    ("B body-adr map   ", lambda j: list(zip(badr, j)))]:
        zs = [wrist_z(fn(q[f])) for f in range(0, len(q), 10)]
        print("   %s : wrist_z %s" % (tag, np.round(zs, 4).tolist()))
