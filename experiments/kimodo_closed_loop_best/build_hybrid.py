"""Build the HYBRID grasp CSV per the user's division of labor:

  frames 0-14   : stand (delivered values)
  frames 15-74  : KIMODO right-arm approach (TF2_seed33, pure in 25-62,
                  smoothstep blend-in from stand 15-24, blend-out to dock 63-74)
  frames 75-119 : CODE dock pose (validated grasp position + wrist orientation)
  frames 120-194: lift = KIMODO wrist-position path (from its own generated
                  trajectory, boundary-blended and end-held) + CODE-pinned
                  wrist orientation (dock quat) via per-frame DLS IK
  root          : fixed [0,0,0.7887] + identity quat, all frames
  left side     : frozen at stand; fingers = delivered hand CSV (code program)

Outputs: hybrid_body_v1.csv (195x36), hybrid_hand_v1.csv (195x14, copy),
         hybrid_build_report.json
"""
import json
import os
import resource

import mujoco
import numpy as np

resource.setrlimit(resource.RLIMIT_AS, (16 * 1024**3, 16 * 1024**3))

OLD = "/data/group4/20261007-000440-workbuddy-55cfbbfeb697e3dd"
NEW = "/data/group4/20261008-232029-workbuddy-34e89f61"
SCENE = os.path.join(OLD, "harness/bridge/g1/scene_grasp_hand.xml")
DELIV = os.path.join(
    "/home/group4/group4_dasc7606c/work"
    "/20261007-000440-workbuddy-55cfbbfeb697e3dd/deliverables")
KIM = os.path.join(OLD, "kimodo_out/bestTF2_seed33.csv")

ROOT = np.array([0.0, 0.0, 0.7887])
DOCK_QUAT = np.array([0.64145, -0.5888, -0.2656, 0.41389])

ARM_NAMES = ["right_shoulder_pitch_joint", "right_shoulder_roll_joint",
             "right_shoulder_yaw_joint", "right_elbow_joint",
             "right_wrist_roll_joint", "right_wrist_pitch_joint",
             "right_wrist_yaw_joint"]

m = mujoco.MjModel.from_xml_path(SCENE)
d = mujoco.MjData(m)
JO = json.load(open(os.path.join(OLD, "joint_order.json")))["sonic_order"]
ADR, DOF = {}, {}
for i in range(m.njnt):
    n = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, i)
    if n:
        ADR[n] = int(m.jnt_qposadr[i])
        DOF[n] = int(m.jnt_dofadr[i])
ARM_Q = [ADR[n] for n in ARM_NAMES]
ARM_DOF = [DOF[n] for n in ARM_NAMES]
ARMCSV = [7 + JO.index(n) for n in ARM_NAMES]
ARM_RANGE = np.array([m.jnt_range[m.joint(n).id] for n in ARM_NAMES])
WB = int(m.body("right_wrist_yaw_link").id)

deliv = np.loadtxt(os.path.join(DELIV, "g1_right_hand_grasp_body_195f30fps.csv"),
                   delimiter=",", dtype=float)
hand = np.loadtxt(os.path.join(DELIV, "g1_right_hand_grasp_hand_195f30fps.csv"),
                  delimiter=",", dtype=float)
kim = np.loadtxt(KIM, delimiter=",", dtype=float)
assert deliv.shape == (195, 36) and hand.shape == (195, 14) and kim.shape == (195, 36)
BASE = deliv[0]
DOCK_ARM = deliv[75, ARMCSV].copy()
STAND_ARM = deliv[0, ARMCSV].copy()
kim_arm = kim[:, ARMCSV]


def fk_wrist(arm_q):
    d.qpos[:] = 0
    d.qpos[0:3] = ROOT
    d.qpos[3:7] = [1, 0, 0, 0]
    for name in JO:
        d.qpos[ADR[name]] = BASE[7 + JO.index(name)]
    for k, adr in enumerate(ARM_Q):
        d.qpos[adr] = arm_q[k]
    mujoco.mj_forward(m, d)
    return d.xpos[WB].copy(), d.xquat[WB].copy()


# kimodo wrist position path under delivery conditions (fixed root, frozen body)
wpos_k = np.zeros((195, 3))
for f in range(195):
    wpos_k[f], _ = fk_wrist(kim_arm[f])
DOCK_POS, _ = fk_wrist(DOCK_ARM)


def smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def blend(a, b, w):
    return (1.0 - w) * a + w * b


# ---------------- build arm trajectory ----------------
arm = np.zeros((195, 7))
arm[0:15] = deliv[0:15, ARMCSV]
for f in range(15, 25):                       # blend-in stand -> kimodo
    w = smoothstep((f - 15) / 9.0)
    arm[f] = blend(STAND_ARM, kim_arm[f], w)
arm[25:63] = kim_arm[25:63]                   # pure Kimodo approach
for f in range(63, 75):                       # blend-out kimodo -> dock
    w = smoothstep((f - 63) / 11.0)
    arm[f] = blend(kim_arm[f], DOCK_ARM, w)
arm[75:120] = DOCK_ARM                        # code dock

# lift: kimodo position path, lightly smoothed, boundary blended, end held
p_raw = wpos_k[120:195].copy()
p_s = p_raw.copy()                            # moving average w=5, pinned ends
for i in range(2, len(p_raw) - 2):
    p_s[i] = p_raw[i - 2:i + 3].mean(axis=0)
p_lift = np.zeros((75, 3))
for i in range(75):
    w = smoothstep(min(i / 9.0, 1.0))         # blend dock -> kimodo over 10f
    p_lift[i] = blend(DOCK_POS, p_s[i], w)
hold = p_lift[67].copy()                      # frame 187
for i in range(68, 75):                       # frames 188-194: ease into hold
    w = smoothstep((i - 67) / 7.0)
    p_lift[i] = blend(p_lift[i], hold, w)


def ik_frame(q_init, p_tgt, quat_tgt, iters=200, lam=1e-3, tol=2e-4):
    q = q_init.copy()
    jacp = np.zeros((3, m.nv))
    jacr = np.zeros((3, m.nv))
    for _ in range(iters):
        wpos, wquat = fk_wrist(q)
        e_p = p_tgt - wpos
        q_neg = np.zeros(4)
        mujoco.mju_negQuat(q_neg, wquat)
        q_err = np.zeros(4)
        mujoco.mju_mulQuat(q_err, quat_tgt, q_neg)
        e_r = np.zeros(3)
        mujoco.mju_quat2Vel(e_r, q_err, 1.0)
        if np.linalg.norm(e_p) < tol and np.linalg.norm(e_r) < 0.01:
            break
        mujoco.mj_jacBody(m, d, jacp, jacr, WB)
        J = np.vstack([jacp[:, ARM_DOF], jacr[:, ARM_DOF]])
        e = np.concatenate([e_p, 0.6 * e_r])
        dq = J.T @ np.linalg.solve(J @ J.T + lam**2 * np.eye(6), e)
        dq = np.clip(dq, -0.25, 0.25)
        q = q + dq
        q = np.clip(q, ARM_RANGE[:, 0] + 0.005, ARM_RANGE[:, 1] - 0.005)
    wpos, wquat = fk_wrist(q)
    return q, float(np.linalg.norm(p_tgt - wpos)), wpos


q = DOCK_ARM.copy()
ik_err = np.zeros(75)
lift_wpos = np.zeros((75, 3))
for i in range(75):
    q, err, wp = ik_frame(q, p_lift[i], DOCK_QUAT)
    arm[120 + i] = q
    ik_err[i] = err
    lift_wpos[i] = wpos_k[120 + i]  # kimodo reference for reporting

# ---------------- assemble body CSV ----------------
body = np.zeros((195, 36))
body[:, 0:3] = ROOT
body[:, 3] = 1.0                            # qw
body[:, 7:36] = BASE[7:36]                  # frozen legs/waist/left arm
body[:, ARMCSV] = arm

# ---------------- self checks ----------------
jump = np.degrees(np.abs(np.diff(arm, axis=0))).max(axis=1)
lim_lo = (arm - ARM_RANGE[:, 0]).min()
lim_hi = (ARM_RANGE[:, 1] - arm).min()
# approach clearance: fingertip sphere centers to cube center
CUBE = np.array([0.267, -0.118, 0.7745])
FT = [int(m.geom(g).id) for g in
      ["right_thumb_fingertip", "right_index_fingertip", "right_middle_fingertip"]]
clr = np.zeros(195)
for f in range(195):
    d.qpos[:] = 0
    d.qpos[0:3] = ROOT
    d.qpos[3:7] = [1, 0, 0, 0]
    for name in JO:
        d.qpos[ADR[name]] = BASE[7 + JO.index(name)]
    for k, adr in enumerate(ARM_Q):
        d.qpos[adr] = arm[f, k]
    for k, nm in enumerate(["right_hand_thumb_0_joint", "right_hand_thumb_1_joint",
                            "right_hand_thumb_2_joint", "right_hand_index_0_joint",
                            "right_hand_index_1_joint", "right_hand_middle_0_joint",
                            "right_hand_middle_1_joint"]):
        d.qpos[ADR[nm]] = hand[f, 7 + k]
    mujoco.mj_forward(m, d)
    pts = np.array([d.geom_xpos[g] for g in FT])
    clr[f] = (np.linalg.norm(pts - CUBE, axis=1) - 0.0275).min() * 1000

wpos_final, _ = fk_wrist(arm[194])
report = {
    "kimodo_source": KIM,
    "segments": {
        "stand": [0, 14], "blend_in": [15, 24], "kimodo_pure_approach": [25, 62],
        "blend_to_dock": [63, 74], "code_dock": [75, 119],
        "lift_kimodo_path_code_orientation": [120, 194]},
    "max_arm_jump_deg": round(float(jump.max()), 2),
    "max_arm_jump_frame": int(jump.argmax()),
    "jump_at_74_75_deg": round(float(jump[74]), 3),
    "jump_at_119_120_deg": round(float(jump[119]), 3),
    "limit_margin_rad": [round(float(lim_lo), 4), round(float(lim_hi), 4)],
    "ik_residual_mm": {"max": round(float(ik_err.max() * 1000), 2),
                       "mean": round(float(ik_err.mean() * 1000), 2)},
    "lift_rise_mm": round(float((wpos_final[2] - DOCK_POS[2]) * 1000), 1),
    "approach_min_fingertip_surface_clr_mm": round(float(clr[10:70].min()), 1),
    "dock_wrist_pos": [round(float(x), 5) for x in DOCK_POS],
    "final_wrist_pos": [round(float(x), 5) for x in wpos_final],
}
np.savetxt(os.path.join(NEW, "hybrid_body_v1.csv"), body, delimiter=",", fmt="%.8f")
np.savetxt(os.path.join(NEW, "hybrid_hand_v1.csv"), hand, delimiter=",", fmt="%.8f")
json.dump(report, open(os.path.join(NEW, "hybrid_build_report.json"), "w"),
          indent=2, ensure_ascii=False)
print(json.dumps(report, indent=2, ensure_ascii=False))
print("WROTE hybrid_body_v1.csv + hybrid_hand_v1.csv + hybrid_build_report.json")
