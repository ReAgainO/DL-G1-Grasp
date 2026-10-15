#!/usr/bin/env python3
"""Which interpretation puts the constrained Kimodo hand at the cube?

FK a 36-column Kimodo qpos CSV through
  (A) the SONIC/harness G1 model (Z-up scene, cube [0.267,-0.118,0.7745])
  (B) Kimodo's own g1skel34/xml/g1.xml  (Y-up)
matching joints BY NAME so the mapping is order-independent, and reporting the
right wrist position relative to the pelvis, anchored at the scene root.

Kimodo<->scene axis mapping used (derived from the SONIC constraint file that
encodes the cube as [scene_y, scene_z, scene_x]):
    scene = (k_z, k_x, k_y)

Usage: fk_cmp.py <scene.xml> <kimodo_g1.xml> <clip.csv> [<clip.csv> ...]
"""
import sys
from pathlib import Path
import mujoco
import numpy as np

SCENE, KG1 = sys.argv[1], sys.argv[2]
CUBE = np.array([0.267, -0.118, 0.7745])
ANCHOR = np.array([0.0, 0.0, 0.7887])

BODY29 = ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint",
          "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint",
          "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint",
          "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint",
          "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint",
          "left_shoulder_pitch_joint", "left_shoulder_roll_joint",
          "left_shoulder_yaw_joint", "left_elbow_joint",
          "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint",
          "right_shoulder_pitch_joint", "right_shoulder_roll_joint",
          "right_shoulder_yaw_joint", "right_elbow_joint",
          "right_wrist_roll_joint", "right_wrist_pitch_joint",
          "right_wrist_yaw_joint"]


def yup_to_zup(v):
    """(k_x,k_y,k_z) -> (s_x,s_y,s_z) = (k_z, k_x, k_y)"""
    return np.array([v[2], v[0], v[1]])


def probe(tag, xml, to_scene):
    m = mujoco.MjModel.from_xml_path(xml)
    d = mujoco.MjData(m)
    adr, lim = [], []
    for nm in BODY29:
        jid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, nm)
        adr.append(int(m.jnt_qposadr[jid]) if jid >= 0 else -1)
        lim.append(m.jnt_range[jid] if jid >= 0 else np.array([-1e9, 1e9]))
    hb = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "right_wrist_yaw_link")
    pb = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
    print("\n### %s   model=%s  (hand body ok=%s)" % (tag, Path(xml).name, hb >= 0 and pb >= 0))
    for path in sys.argv[3:]:
        a = np.loadtxt(path, delimiter=",")
        if a.ndim == 1:
            a = a[None]
        excess, worst, r = 0.0, None, []
        for f in a:
            d.qpos[:] = 0.0
            d.qpos[:3] = [0, 0, 0]
            d.qpos[3:7] = [1, 0, 0, 0]
            for k, ad in enumerate(adr):
                if ad < 0:
                    continue
                v = float(f[7 + k])
                d.qpos[ad] = v
                e = max(float(lim[k][0]) - v, v - float(lim[k][1]), 0.0)
                if e > excess:
                    excess, worst = e, (BODY29[k], v, float(lim[k][0]), float(lim[k][1]))
            mujoco.mj_forward(m, d)
            rel = d.xpos[hb] - d.xpos[pb]
            r.append(to_scene(rel) + ANCHOR)
        r = np.asarray(r)
        dist = np.linalg.norm(r - CUBE, axis=1)
        k = int(np.argmin(dist))
        print("   %-26s min|wrist-cube|=%.0f mm @f%d/%d  wrist_z %.3f..%.3f"
              % (Path(path).name, dist[k] * 1000, k, len(a), r[:, 2].min(), r[:, 2].max()))
        print("      worst limit excess %.3f rad %s" % (excess, worst))


probe("A SONIC/harness model (already Z-up)", SCENE, lambda v: v)
probe("B Kimodo own g1.xml (Y-up -> Z-up)", KG1, yup_to_zup)
