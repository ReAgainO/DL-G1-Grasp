#!/usr/bin/env python3
"""Forward-kinematics probe: does a candidate approach clip actually bring the
right hand to the cube?  Root is pinned to the scenario anchor.

Usage: kimo_fk_probe.py <scene.xml> <clip.npz> [<clip.npz> ...]
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
ORDER = ["right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint",
         "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"]
ADR = [int(m.jnt_qposadr[m.joint(n).id]) for n in ORDER]
WB = int(m.body("right_wrist_yaw_link").id)

for spec in sys.argv[2:]:
    p = Path(spec)
    mm = mi.ArdyMotion(p)
    q = mm.qpos
    wrist = []
    for f in range(len(q)):
        d.qpos[:] = 0.0
        d.qpos[:3] = ANCHOR
        d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[7:36] = q[f, 7:]
        mujoco.mj_forward(m, d)
        wrist.append(d.xpos[WB].copy())
    wrist = np.asarray(wrist)
    dist = np.linalg.norm(wrist - CUBE, axis=1)
    k = int(np.argmin(dist))
    print("%-26s T=%d" % (p.stem, len(q)))
    print("   wrist min/max xyz: %s .. %s" % (np.round(wrist.min(0), 3).tolist(),
                                               np.round(wrist.max(0), 3).tolist()))
    print("   closest wrist->cube: %.1f mm at frame %d  wrist=%s"
          % (dist[k] * 1000, k, np.round(wrist[k], 4).tolist()))
    print("   wrist height range: %.3f .. %.3f (excursion %.1f mm)"
          % (wrist[:, 2].min(), wrist[:, 2].max(), (wrist[:, 2].max() - wrist[:, 2].min()) * 1000))
    print("   arm joints first frame:", np.round(q[0, 29:36], 3).tolist())
    print("   arm joints last  frame:", np.round(q[-1, 29:36], 3).tolist())
    print("   arm joint travel      :", np.round(q[:, 29:36].max(0) - q[:, 29:36].min(0), 3).tolist())
