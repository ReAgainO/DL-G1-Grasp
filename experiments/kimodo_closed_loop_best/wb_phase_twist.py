"""Where does the clip difference survive into the simulation?

The whole-run metric washed out because the harness replans the arm. To find out
whether the natural clip still helps anything, split the rollout by phase and
recompute the hand-roll metric inside each phase.

If the difference appears in APPROACH/PREGRASP but not in DESCEND/CLOSE, then the
Kimodo prior matters early and the harness overrides it late.
"""
import numpy as np
import os
import sys

B = "/data/group4/20261008-232029-workbuddy-34e89f61"
R = os.path.join(B, "harness_s1000", "rep")
sys.path.insert(0, R)
import mujoco  # noqa: E402


def bid(model, name):
    return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)


def roll_series(cell):
    d = os.path.join(R, "out", cell)
    model = mujoco.MjModel.from_xml_path(os.path.join(d, "scene.xml"))
    data = mujoco.MjData(model)
    z = np.load(os.path.join(d, "trajectory.npz"))
    qpos, phase = z["qpos"], z["phase"]

    wrist = bid(model, "right_wrist_yaw_link")
    elbow = bid(model, "right_elbow_link")
    hand = bid(model, "right_hand_index_1_link")

    roll = np.zeros(qpos.shape[0])
    hd_ang = np.zeros(qpos.shape[0])
    prev = None
    for i in range(qpos.shape[0]):
        data.qpos[:] = qpos[i]
        mujoco.mj_forward(model, data)
        p_el = data.xpos[elbow].copy()
        p_wr = data.xpos[wrist].copy()
        p_hd = data.xpos[hand].copy()
        hd = p_hd - p_wr
        hd = hd / (np.linalg.norm(hd) + 1e-12)
        hd_ang[i] = np.degrees(np.arccos(np.clip(hd[2] * -1, -1, 1)))
        fa = (p_wr - p_el); fa = fa / (np.linalg.norm(fa) + 1e-12)
        ref = np.array([0.0, 0.0, 1.0])
        n = np.cross(fa, ref); n = n / (np.linalg.norm(n) + 1e-12)
        bb = np.cross(fa, n); bb = bb / (np.linalg.norm(bb) + 1e-12)
        r = np.arctan2(np.dot(hd, bb), np.dot(hd, n))
        if prev is not None:
            roll[i] = abs(np.arctan2(np.sin(r - prev), np.cos(r - prev)))
        prev = r
    return roll, hd_ang, phase


r1, h1, ph1 = roll_series("wb_kimo_p6l1")
r2, h2, ph2 = roll_series("wb_nat_n4l1")

names = [str(x) for x in ph1]
order = []
for n in names:
    if n not in order:
        order.append(n)

print("=" * 100)
print("PER-PHASE HAND ROLL (deg) AND PALM-DOWN ANGLE -- delivered p6l1 vs natural n4l1")
print("=" * 100)
print("%-16s %-10s %-22s %-22s %s" %
      ("phase", "frames", "roll p6l1 -> n4l1", "hand_down p6l1 -> n4l1", "delta roll"))
print("-" * 100)
for n in order:
    m = np.array([x == n for x in names])
    if not m.any():
        continue
    a = np.degrees(r1[m]).sum()
    b = np.degrees(r2[m]).sum()
    ha = h1[m].mean()
    hb = h2[m].mean()
    print("%-16s %-10d %-22s %-22s %+.1f" %
          (n, int(m.sum()),
           "%.1f -> %.1f" % (a, b),
           "%.1f -> %.1f" % (ha, hb),
           b - a))
