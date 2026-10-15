#!/usr/bin/env python3
"""NAT-EXP 2 outcome reader.

Cells produced by wb_nat2_sweep.sh, named wb_nat2_<clip>_<on|off>.

Reports per cell:
  - success / gates (from result.json)
  - max_lift_m
  - wrist metrics recomputed from the FINAL trajectory.npz via MuJoCo FK:
      total_roll_deg  (integrated frame-to-frame hand roll about the forearm axis)
      hand_down_deg   (hand axis angle from straight down)
      elbow_bend_deg  (interior elbow angle, 180 = straight)
  - provenance (pinch_native_orientation, motion_stem) from raw/<cell>.meta.txt

Run:  cd harness_nat/rep && MUJOCO_GL=disable PYTHONPATH=. python wb_nat2_read.py
"""
import glob
import json
import os

import numpy as np
import mujoco

R = "/data/group4/20261008-232029-workbuddy-34e89f61/harness_nat/rep"
WRIST, ELBOW, SHOULDER, HAND = ("right_wrist_yaw_link", "right_elbow_link",
                                "right_shoulder_pitch_link", "right_hand_index_1_link")


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def trajectory_metrics(path):
    z = np.load(path, allow_pickle=True)
    qpos = z["qpos"]
    m = mujoco.MjModel.from_xml_path(str(z["scene"]))
    d = mujoco.MjData(m)
    iw = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, WRIST)
    ie = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, ELBOW)
    ish = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, SHOULDER)
    ih = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, HAND)
    ax, fx, elb = [], [], []
    for q in qpos:
        d.qpos[:] = q
        mujoco.mj_forward(m, d)
        pw, pe, ps, ph = d.xpos[iw], d.xpos[ie], d.xpos[ish], d.xpos[ih]
        ax.append(unit(ph - pw))
        fx.append(unit(pw - pe))
        elb.append(np.degrees(np.arccos(np.clip(np.dot(unit(ps - pe), unit(pw - pe)), -1, 1))))
    ax, fx = np.array(ax), np.array(fx)
    elb = np.array(elb)
    total = 0.0
    for i in range(1, len(ax)):
        f = unit(fx[i - 1] + fx[i])
        a0 = ax[i - 1] - np.dot(ax[i - 1], f) * f
        a1 = ax[i] - np.dot(ax[i], f) * f
        n0, n1 = np.linalg.norm(a0), np.linalg.norm(a1)
        if n0 > 1e-9 and n1 > 1e-9:
            total += np.degrees(np.arccos(np.clip(np.dot(a0 / n0, a1 / n1), -1, 1)))
    hand_down = float(np.degrees(np.arccos(np.clip(-ax[:, 2], -1, 1))).mean())
    return float(total), hand_down, float(elb.mean())


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
    for d in sorted(glob.glob(os.path.join(R, "out", "wb_nat2_*"))):
        name = os.path.basename(d)
        meta = os.path.join(R, "..", "raw", name + ".meta.txt")
        row = {"cell": name,
               "stem": meta_get(meta, "motion_stem"),
               "native_orient": meta_get(meta, "pinch_native_orientation")}
        rj, tz = os.path.join(d, "result.json"), os.path.join(d, "trajectory.npz")
        if os.path.exists(rj):
            r = json.load(open(rj))
            g = r.get("gates", {})
            row["success"] = r.get("success")
            row["gates_pass"] = sum(1 for v in g.values() if v)
            row["failed"] = [k for k, v in g.items() if not v]
            row["max_lift_m"] = r.get("max_lift_m")
            row["table_N"] = r.get("robot_table_all_max_normal_N")
        else:
            row["success"] = None
            row["failed"] = ["NO_RESULT_JSON"]
        if os.path.exists(tz):
            try:
                t, hd, e = trajectory_metrics(tz)
                row["total_roll_deg"] = round(t, 2)
                row["hand_down_deg"] = round(hd, 2)
                row["elbow_bend_deg"] = round(e, 2)
            except Exception as ex:  # noqa: BLE001
                row["err"] = f"{type(ex).__name__}: {ex}"
        rows.append(row)
    print(json.dumps(rows, indent=1, default=str))
    out = "/data/group4/20261008-232029-workbuddy-34e89f61/nat2_sweep.json"
    json.dump(rows, open(out, "w"), indent=1, default=str)
    print("WROTE", out)


if __name__ == "__main__":
    main()
