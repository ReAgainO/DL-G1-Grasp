"""Hybrid-aware measurement of Kimodo candidates (name-driven qpos mapping).

CRITICAL mapping fact (diagnosed this round): the scene model inserts the 7
LEFT finger joints at qpos 29..35, so the right arm lives at qpos 36..42 and
right fingers at 43..49. Any positional block assignment qpos[7:36]=csv[7:36]
silently lands right-arm values on left fingers. Everything below maps by
joint NAME via m.jnt_qposadr.

Replays each candidate's RIGHT ARM 7 columns under final delivery conditions:
root fixed [0,0,0.7887] + identity quat, all other body joints frozen at the
delivered frame-0 pose, right fingers = delivered hand CSV (open during
approach). Measures approach blendability/safety and lift profile.
"""
import json
import os

import mujoco
import numpy as np

OLD = "/data/group4/20261007-000440-workbuddy-55cfbbfeb697e3dd"
SCENE = os.path.join(OLD, "harness/bridge/g1/scene_grasp_hand.xml")
DELIV = os.path.join(
    "/home/group4/group4_dasc7606c/work"
    "/20261007-000440-workbuddy-55cfbbfeb697e3dd/deliverables")
DELIV_BODY = os.path.join(DELIV, "g1_right_hand_grasp_body_195f30fps.csv")
DELIV_HAND = os.path.join(DELIV, "g1_right_hand_grasp_hand_195f30fps.csv")

DOCK_POS = np.array([0.20256, -0.22152, 0.87778])
DOCK_QUAT = np.array([0.64145, -0.5888, -0.2656, 0.41389])  # wxyz
ROOT = np.array([0.0, 0.0, 0.7887])

CANDS = [
    ("TF1_sd11", os.path.join(OLD, "kimodo_out/bestTF1_seed11.csv")),
    ("TF2_sd33", os.path.join(OLD, "kimodo_out/bestTF2_seed33.csv")),
    ("EE_s400_sd33", os.path.join(OLD, "kimodo_out/EE_s400_sd33.csv")),
    ("gm_s400_sd33", os.path.join(OLD, "kimodo_out/gm_s400_seed33.csv")),
    ("DELIVERED", DELIV_BODY),
]

ARM_NAMES = ["right_shoulder_pitch_joint", "right_shoulder_roll_joint",
             "right_shoulder_yaw_joint", "right_elbow_joint",
             "right_wrist_roll_joint", "right_wrist_pitch_joint",
             "right_wrist_yaw_joint"]
RFING_NAMES = ["right_hand_thumb_0_joint", "right_hand_thumb_1_joint",
               "right_hand_thumb_2_joint", "right_hand_index_0_joint",
               "right_hand_index_1_joint", "right_hand_middle_0_joint",
               "right_hand_middle_1_joint"]

m = mujoco.MjModel.from_xml_path(SCENE)
d = mujoco.MjData(m)
JO = json.load(open(os.path.join(OLD, "joint_order.json")))["sonic_order"]

ADR = {}
for i in range(m.njnt):
    n = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, i)
    if n:
        ADR[n] = int(m.jnt_qposadr[i])
ARM_Q = [ADR[n] for n in ARM_NAMES]
RFING_Q = [ADR[n] for n in RFING_NAMES]
ARMCSV = [7 + JO.index(n) for n in ARM_NAMES]
BODY_Q = {n: ADR[n] for n in JO}          # every body joint -> qpos address
WB = int(m.body("right_wrist_yaw_link").id)

RIGHT_BODIES = set()
for i in range(m.nbody):
    n = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i) or ""
    if n.startswith("right_hand_") or n in (
            "right_shoulder_pitch_link", "right_shoulder_roll_link",
            "right_shoulder_yaw_link", "right_elbow_link",
            "right_wrist_roll_link", "right_wrist_pitch_link",
            "right_wrist_yaw_link"):
        RIGHT_BODIES.add(i)
RIGHT_GEOMS = [g for g in range(m.ngeom)
               if int(m.geom_bodyid[g]) in RIGHT_BODIES]
CUBE_G = int(m.geom("red_cube_geom").id)

deliv = np.loadtxt(DELIV_BODY, delimiter=",", dtype=float)
hand = np.loadtxt(DELIV_HAND, delimiter=",", dtype=float)
BASE = deliv[0].copy()


def replay(arm_cols):
    n = arm_cols.shape[0]
    wpos = np.zeros((n, 3))
    wquat = np.zeros((n, 4))
    clear = np.zeros(n)
    fromto = np.zeros(6)
    for f in range(n):
        d.qpos[:] = 0
        d.qpos[0:3] = ROOT
        d.qpos[3:7] = [1, 0, 0, 0]
        for name, adr in BODY_Q.items():          # frozen body pose
            d.qpos[adr] = BASE[7 + JO.index(name)]
        for k, adr in enumerate(ARM_Q):           # candidate right arm
            d.qpos[adr] = arm_cols[f, k]
        for k, adr in enumerate(RFING_Q):         # real finger pose
            d.qpos[adr] = hand[f, 7 + k]
        mujoco.mj_forward(m, d)
        wpos[f] = d.xpos[WB]
        wquat[f] = d.xquat[WB]
        best = 1e9
        for g in RIGHT_GEOMS:
            r = mujoco.mj_geomDistance(m, d, g, CUBE_G, 0.20, fromto)
            if r < best:
                best = r
        clear[f] = best
    return wpos, wquat, clear


def quat_angle(q1, q2):
    q1 = q1 / np.linalg.norm(q1)
    q2 = q2 / np.linalg.norm(q2)
    return 2.0 * np.degrees(np.arccos(min(1.0, abs(float(np.dot(q1, q2))))))


# sanity: delivered replay must reproduce the dock (wrist-to-dock ~0 in 75-119)
print("%-13s %8s %8s %8s | %8s %8s %8s %7s | %7s" %
      ("candidate", "app_end", "clr_app", "jump75",
       "L120err", "Lz_rise", "Lw_ori", "Lw_max", "jump"))
results = {}
for name, path in CANDS:
    q = np.loadtxt(path, delimiter=",", dtype=float)
    arm = q[:, ARMCSV]
    wpos, wquat, clear = replay(arm)
    dw = np.linalg.norm(wpos - DOCK_POS, axis=1) * 1000
    jump = np.degrees(np.abs(np.diff(arm, axis=0))).max()
    j75 = float(np.degrees(np.abs(arm[74] - deliv[75, ARMCSV]).max()))
    ori_seq = [quat_angle(wquat[f + 1], wquat[f]) for f in range(120, 194)]
    lz = (wpos[120:195, 2].max() - wpos[120, 2]) * 1000
    results[name] = dict(dw=dw, clear=clear, wpos=wpos, wquat=wquat)
    print("%-13s %7.1fmm %7.1fmm %7.1fd | %7.1fmm %7.1fmm %7.1fd %6.1fd | %6.1fd"
          % (name, dw[70:75].min(), clear[10:75].min() * 1000, j75,
             dw[120], lz, quat_angle(wquat[120], DOCK_QUAT),
             max(ori_seq), jump))
print()
for name, path in CANDS:
    dw = results[name]["dw"]
    print("%-13s dock-zone(75-119): min=%.1f mean=%.1f max=%.1f mm"
          % (name, dw[75:120].min(), dw[75:120].mean(), dw[75:120].max()))
print()
print("legend: app_end=min wrist-to-dock frames70-74; clr_app=min right-side")
print("  geom clearance to cube frames10-74 (>0 required); jump75=arm angle")
print("  gap vs dock frame75; L120err=wrist-to-dock @120; Lz_rise=wrist z")
print("  rise during lift; Lw_ori=wrist orientation vs dock @120 (deg);")
print("  Lw_max=max per-frame orientation step during lift; jump=max")
print("  per-frame arm joint jump (deg)")
