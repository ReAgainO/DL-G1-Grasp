"""Build hybrid V2 grasp body CSV for the OFFICIAL SonicPolicy tracker.

Design (per user's division of labor):
  frames 0-14   : stand (delivered values)
  frames 15-24  : blend stand -> Kimodo
  frames 25-54  : KIMODO right-arm approach (TF2_seed33, pure)
  frames 55-65  : blend Kimodo -> dock (finish EARLY so the tracker settles
                  before fingers close at t=2.5s / frame 75)
  frames 65-119 : CODE dock hold (validated grasp pos/wrist orientation),
                  plus joint-space compensation vector `comp` (iteration
                  pre-compensation against the official tracker)
  frames 120-130: blend dock(+comp) -> Kimodo lift
  frames 131-188: KIMODO lift (pure, plus optional lift compensation)
  frames 189-194: ease into constant hold
  root          : fixed [0,0,0.7887] + identity quat
  legs/waist/left arm: frozen at stand; fingers come from the runner's own
                  PD program (--hand-open/--hand-closed)

Usage: build_v2.py <out_csv> <comp_json>   # comp_json: {"comp":[7 floats]}
"""
import json
import os
import sys

import mujoco
import numpy as np

OLD = "/data/group4/20261007-000440-workbuddy-55cfbbfeb697e3dd"
NEW = "/data/group4/20261008-232029-workbuddy-34e89f61"
SCENE = os.path.join(OLD, "harness/bridge/g1/scene_grasp_hand.xml")
DELIV = os.path.join(
    "/home/group4/group4_dasc7606c/work"
    "/20261007-000440-workbuddy-55cfbbfeb697e3dd/deliverables")
KIM = os.path.join(OLD, "kimodo_out/bestTF2_seed33.csv")

ROOT = np.array([0.0, 0.0, 0.7887])
ARM_NAMES = ["right_shoulder_pitch_joint", "right_shoulder_roll_joint",
             "right_shoulder_yaw_joint", "right_elbow_joint",
             "right_wrist_roll_joint", "right_wrist_pitch_joint",
             "right_wrist_yaw_joint"]

m = mujoco.MjModel.from_xml_path(SCENE)
d = mujoco.MjData(m)
JO = json.load(open(os.path.join(OLD, "joint_order.json")))["sonic_order"]
ADR = {}
for i in range(m.njnt):
    n = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, i)
    if n:
        ADR[n] = int(m.jnt_qposadr[i])
ARM_Q = [ADR[n] for n in ARM_NAMES]
ARMCSV = [7 + JO.index(n) for n in ARM_NAMES]
ARM_RANGE = np.array([m.jnt_range[m.joint(n).id] for n in ARM_NAMES])

deliv = np.loadtxt(os.path.join(DELIV, "g1_right_hand_grasp_body_195f30fps.csv"),
                   delimiter=",", dtype=float)
kim = np.loadtxt(KIM, delimiter=",", dtype=float)
BASE = deliv[0]
STAND_ARM = deliv[0, ARMCSV].copy()
DOCK_ARM = deliv[75, ARMCSV].copy()
kim_arm = kim[:, ARMCSV]

OUT = sys.argv[1]
comp = np.zeros(7)
lift_dz = 0.0
if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
    cfg = json.load(open(sys.argv[2]))
    comp = np.array(cfg.get("comp", [0.0] * 7), dtype=float)
    lift_dz = float(cfg.get("lift_dz", 0.0))
DOCK_COMP = DOCK_ARM + comp
over_lo = (ARM_RANGE[:, 0] + 0.02 - DOCK_COMP).clip(min=0)
over_hi = (DOCK_COMP - ARM_RANGE[:, 1] + 0.02).clip(min=0)
DOCK_COMP = DOCK_COMP + over_lo - over_hi     # keep 0.02 rad limit margin


def smoothstep(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


arm = np.zeros((195, 7))
arm[0:15] = deliv[0:15, ARMCSV]
for f in range(15, 25):
    w = smoothstep((f - 15) / 9.0)
    arm[f] = (1 - w) * STAND_ARM + w * kim_arm[f]
arm[25:55] = kim_arm[25:55]                   # pure Kimodo approach
for f in range(55, 66):                       # blend kimodo -> dock(+comp)
    w = smoothstep((f - 55) / 10.0)
    arm[f] = (1 - w) * kim_arm[f] + w * DOCK_COMP
arm[66:120] = DOCK_COMP                       # settled dock hold
for f in range(120, 131):                     # blend dock -> kimodo lift
    w = smoothstep((f - 120) / 10.0)
    arm[f] = (1 - w) * DOCK_COMP + w * kim_arm[f]
arm[131:189] = kim_arm[131:189]               # pure Kimodo lift
for f in range(189, 195):                     # ease into hold
    w = smoothstep((f - 188) / 6.0)
    arm[f] = (1 - w) * kim_arm[f] + w * kim_arm[188]

body = np.zeros((195, 36))
body[:, 0:3] = ROOT
body[:, 3] = 1.0
body[:, 7:36] = BASE[7:36]
body[:, ARMCSV] = arm
np.savetxt(OUT, body, delimiter=",", fmt="%.8f")

jump = np.degrees(np.abs(np.diff(arm, axis=0))).max(axis=1)
print(json.dumps({
    "out": OUT,
    "comp": [round(float(x), 5) for x in comp],
    "max_jump_deg": round(float(jump.max()), 2),
    "max_jump_frame": int(jump.argmax()),
    "dock_arm": [round(float(x), 5) for x in DOCK_COMP],
    "limit_margin_rad": [round(float((arm - ARM_RANGE[:, 0]).min()), 4),
                         round(float((ARM_RANGE[:, 1] - arm).min()), 4)],
}))
print("WROTE", OUT)
