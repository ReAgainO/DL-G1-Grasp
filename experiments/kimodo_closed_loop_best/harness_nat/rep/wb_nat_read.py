#!/usr/bin/env python3
"""NAT-EXP outcome reader.

For every wb_nat_r* cell produced by wb_nat_sweep.sh:
  - 20 gates + success from result.json
  - lift height, robot-table normal force
  - wrist twist metrics recomputed from the FINAL trajectory.npz via MuJoCo FK
    (total_roll = integrated frame-to-frame hand roll about the forearm axis,
     hand_down  = angle of the hand axis from straight down,
     elbow_bend = interior angle at the elbow, 180 = straight)
  - provenance (flat_pinch_relax) read from raw/<cell>.meta.txt

Run with:  cd harness_nat/rep && MUJOCO_GL=disable PYTHONPATH=. python wb_nat_read.py
"""
import glob
import json
import os
import sys

import numpy as np
import mujoco

R = "/data/group4/20261008-232029-workbuddy-34e89f61/harness_nat/rep"

WRIST = "right_wrist_yaw_link"
ELBOW = "right_elbow_link"
SHOULDER = "right_shoulder_pitch_link"
HAND = "right_hand_index_1_link"


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def twist_metrics(model, data, qpos):
    """Returns (total_roll_deg, hand_down_deg, elbow_bend_deg)."""
    mujoco.mj_kinematics(model, data)
    data.qpos[:] = qpos
    mujoco.mj_forward(model, data)

    def bid(name):
        return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)

    iw, ie, ish, ih = bid(WRIST), bid(ELBOW), bid(SHOULDER), bid(HAND)
    pw = data.xpos[iw].copy()
    pe = data.xpos[ie].copy()
    ps = data.xpos[ish].copy()
    ph = data.xpos[ih].copy()

    # hand pointing axis = index finger link - wrist, projected off the forearm
    fwd = unit(ph - pw)
    # forearm axis
    fa = unit(pw - pe)

    total_roll = 0.0
    prev = None
    # recompute over the trajectory in the caller instead; single frame here
    return fwd, fa, pw, pe, ps, ph


def trajectory_roll(path):
    z = np.load(path, allow_pickle=True)
    qpos = z["qpos"]
    scene = str(z["scene"]) if "scene" in z else None
    model = mujoco.MjModel.from_xml_path(scene)
    data = mujoco.MjData(model)

    iw = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, WRIST)
    ie = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, ELBOW)
    ish = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, SHOULDER)
    ih = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, HAND)

    ax = []      # hand forward axis
    fx = []      # forearm axis
    elb = []     # elbow bend angle
    for q in qpos:
        data.qpos[:] = q
        mujoco.mj_forward(model, data)
        pw = data.xpos[iw].copy()
        pe = data.xpos[ie].copy()
        ps = data.xpos[ish].copy()
        ph = data.xpos[ih].copy()
        ax.append(unit(ph - pw))
        fx.append(unit(pw - pe))
        # interior angle at the elbow: shoulder->elbow vs wrist->elbow
        v1 = unit(ps - pe)
        v2 = unit(pw - pe)
        elb.append(np.degrees(np.arccos(np.clip(np.dot(v1, v2), -1, 1))))
    ax = np.array(ax)
    fx = np.array(fx)
    elb = np.array(elb)

    # total_roll: integrate the component of the frame-to-frame axis change
    # that is perpendicular to the forearm (pure roll about the forearm axis)
    total = 0.0
    for i in range(1, len(ax)):
        f = unit(fx[i - 1] + fx[i])
        a0 = ax[i - 1] - np.dot(ax[i - 1], f) * f
        a1 = ax[i] - np.dot(ax[i], f) * f
        n0, n1 = np.linalg.norm(a0), np.linalg.norm(a1)
        if n0 > 1e-9 and n1 > 1e-9:
            c = np.clip(np.dot(a0 / n0, a1 / n1), -1, 1)
            total += np.degrees(np.arccos(c))
    hand_down = np.degrees(np.arccos(np.clip(-ax[:, 2], -1, 1))).mean()
    return total, hand_down, elb.mean(), scene


def meta_get(path, key):
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    except OSError:
        return None
    return None


def main():
    rows = []
    for d in sorted(glob.glob(os.path.join(R, "out", "wb_nat_r*"))):
        name = os.path.basename(d)
        rj = os.path.join(d, "result.json")
        tz = os.path.join(d, "trajectory.npz")
        row = {"cell": name}
        row["relax"] = meta_get(os.path.join(R, "..", "raw", name + ".meta.txt"),
                                "flat_pinch_relax")
        if os.path.exists(rj):
            r = json.load(open(rj))
            g = r.get("gates", {})
            row["success"] = r.get("success")
            row["gates_pass"] = sum(1 for v in g.values() if v)
            row["gates_total"] = len(g)
            row["failed"] = [k for k, v in g.items() if not v]
            row["max_lift_m"] = r.get("max_lift_m") or r.get("lifted_height_m")
            row["table_N"] = r.get("robot_table_all_max_normal_N")
        else:
            row["success"] = None
            row["gates_pass"] = None
            row["failed"] = ["NO_RESULT_JSON"]
        if os.path.exists(tz):
            try:
                tot, hd, elb, scene = trajectory_roll(tz)
                row["total_roll_deg"] = round(float(tot), 2)
                row["hand_down_deg"] = round(float(hd), 2)
                row["elbow_bend_deg"] = round(float(elb), 2)
            except Exception as e:  # noqa: BLE001
                row["roll_err"] = f"{type(e).__name__}: {e}"
        rows.append(row)

    print(json.dumps(rows, indent=1, default=str))
    out = "/data/group4/20261008-232029-workbuddy-34e89f61/nat_sweep.json"
    json.dump(rows, open(out, "w"), indent=1, default=str)
    print("WROTE", out)


if __name__ == "__main__":
    main()
