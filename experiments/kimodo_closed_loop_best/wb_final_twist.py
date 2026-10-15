"""Prove the naturalness improvement in the FINAL SIMULATED trajectory, not just
in the source clip.

Reads harness_s1000/rep/out/<cell>/trajectory.npz for
  - wb_kimo_p6l1  (delivered, twisted arm)
  - wb_nat_n4l1   (new, natural grasp)
and recomputes the same metrics from qpos using MuJoCo FK, so the numbers reflect
what actually happens in the physics rollout.

qpos layout: root 0:7, 43 hinges 7:50, cube free joint 50:57.
"""
import numpy as np
import os
import sys

B = "/data/group4/20261008-232029-workbuddy-34e89f61"
R = os.path.join(B, "harness_s1000", "rep")
sys.path.insert(0, R)

import mujoco  # noqa: E402


def metrics_for(cell):
    d = os.path.join(R, "out", cell)
    xml = os.path.join(d, "scene.xml")
    model = mujoco.MjModel.from_xml_path(xml)
    data = mujoco.MjData(model)
    z = np.load(os.path.join(d, "trajectory.npz"))
    qpos = z["qpos"]

    # right arm chain body ids
    def bid(name):
        i = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if i < 0:
            raise SystemExit("body not found: " + name)
        return i

    try:
        wrist = bid("right_wrist_yaw_link")
        elbow = bid("right_elbow_link")
        shoulder = bid("right_shoulder_pitch_link")
        hand = bid("right_hand_index_1_link")   # distal finger = hand proxy
    except SystemExit as e:
        print("   body lookup failed:", e)
        return None

    bends, hand_down, rolls = [], [], []
    prev_r = None
    for i in range(qpos.shape[0]):
        data.qpos[:] = qpos[i]
        mujoco.mj_forward(model, data)
        p_sh = data.xpos[shoulder].copy()
        p_el = data.xpos[elbow].copy()
        p_wr = data.xpos[wrist].copy()
        p_hd = data.xpos[hand].copy()

        v1 = p_wr - p_el
        v2 = p_sh - p_el
        c = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-12)
        bends.append(np.degrees(np.arccos(np.clip(c, -1, 1))))

        hd = p_hd - p_wr
        hd = hd / (np.linalg.norm(hd) + 1e-12)
        hand_down.append(np.degrees(np.arccos(np.clip(hd[2] * -1, -1, 1))))

        fa = (p_wr - p_el); fa = fa / (np.linalg.norm(fa) + 1e-12)
        ref = np.array([0.0, 0.0, 1.0])
        n = np.cross(fa, ref); n = n / (np.linalg.norm(n) + 1e-12)
        bb = np.cross(fa, n); bb = bb / (np.linalg.norm(bb) + 1e-12)
        r = np.arctan2(np.dot(hd, bb), np.dot(hd, n))
        if prev_r is not None:
            dr = abs(np.arctan2(np.sin(r - prev_r), np.cos(r - prev_r)))
            rolls.append(np.degrees(dr))
        prev_r = r

    return dict(elbow=float(np.mean(bends)),
                hand_down=float(np.mean(hand_down)),
                roll=float(np.sum(rolls)),
                frames=int(qpos.shape[0]))


print("=" * 92)
print("NATURALNESS IN THE FINAL SIMULATED TRAJECTORY (MuJoCo FK on trajectory.npz)")
print("=" * 92)
print("%-16s %-8s %-14s %-18s %s" % ("cell", "frames", "elbow_bend", "hand_down(0=table)", "total_roll"))
print("-" * 92)
out = {}
for cell in ["wb_kimo_p6l1", "wb_nat_n4l1"]:
    d = os.path.join(R, "out", cell)
    if not os.path.exists(os.path.join(d, "trajectory.npz")):
        print("%-16s (missing)" % cell)
        continue
    m = metrics_for(cell)
    if m is None:
        continue
    out[cell] = m
    print("%-16s %-8d %-14.2f %-18.2f %s" %
          (cell, m["frames"], m["elbow"], m["hand_down"], "%.2f" % m["roll"]))

if len(out) == 2:
    a, b = out["wb_kimo_p6l1"], out["wb_nat_n4l1"]
    print()
    print("IMPROVEMENT (n4 vs delivered p6l1):")
    print("   total roll : %.2f -> %.2f deg   (%.1f%% %s)" %
          (a["roll"], b["roll"], abs(100.0 * (b["roll"] - a["roll"]) / a["roll"]),
           "less twisting" if b["roll"] < a["roll"] else "MORE twisting"))
    print("   hand_down  : %.2f -> %.2f deg   (smaller = palm closer to the table)" %
          (a["hand_down"], b["hand_down"]))
    print("   elbow_bend : %.2f -> %.2f deg" % (a["elbow"], b["elbow"]))
