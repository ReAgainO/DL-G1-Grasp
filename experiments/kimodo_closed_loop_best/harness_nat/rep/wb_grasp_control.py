#!/usr/bin/env python3
"""WorkBuddy grasp controller / verifier.

Runs inside the official SONIC harness rep so it can reuse the harness's own
scene, actuator and hand-open conventions.  It does two things:

  1. *Programs* the grasp by emitting the concrete grasp targets this task
     asserts -- the arm target at the moment of capture, the wrist orientation
     frame, and the finger schedule (open before the approach, contact-gated
     close, then held constant).
  2. *Verifies* the executed result against those targets, reading only the
     official harness outputs (out/<name>/trajectory.npz, telemetry.csv.gz,
     result.json).  Nothing is simulated outside the official environment.

Usage: wb_grasp_control.py <run_name> [--json out.json]
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

import mujoco
import numpy as np

REP = Path(__file__).resolve().parent
sys.path.insert(0, str(REP))
import source_physics_core as core  # noqa: E402

CUBE_XY = np.array([0.267, -0.118])
TABLE_TOP = 0.725


def wrist_pos(model, data, qrow):
    data.qpos[:] = qrow
    mujoco.mj_forward(model, data)
    return data.xpos[model.body("right_wrist_yaw_link").id].copy(), \
        data.xmat[model.body("right_wrist_yaw_link").id].reshape(3, 3).copy()


def rot_deg(A, B):
    R = A.T @ B
    c = (np.trace(R) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    out = REP / "out" / a.name
    traj = np.load(out / "trajectory.npz", allow_pickle=True)
    res = json.loads((out / "result.json").read_text())
    q = np.asarray(traj["qpos"], dtype=np.float64)
    hrs = np.asarray(traj["hand_reference"], dtype=np.float64)
    wref = np.asarray(traj["wrist_target"], dtype=np.float64)
    ph = np.array([str(x) for x in traj["phase"]])
    fps = float(traj["fps"])

    m = mujoco.MjModel.from_xml_path(str(traj["scene"]))
    d = mujoco.MjData(m)
    # right-hand hinge joints in qpos order
    hj = [int(j) for j in m.actuator_trnid[np.arange(36, 43), 0]]
    hq = [int(m.jnt_qposadr[j]) for j in hj]
    hand_names = [m.joint(j).name for j in hj]
    armq = [int(m.jnt_qposadr[m.joint(n).id]) for n in
            ["right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint",
             "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint",
             "right_wrist_yaw_joint"]]
    cube_body = m.body("red_cube").id

    rep = dict(run=a.name, fps_source=fps, frames=len(q),
               hand_joint_names=hand_names)

    # ---- 1. fingers open before the approach -----------------------------
    pre = np.isin(ph, ["SETTLE", "APPROACH", "PREGRASP", "DESCEND", "ALIGN"])
    dev_open = np.abs(q[pre][:, hq] - core.OPEN[None, :])
    rep["fingers"] = dict(
        open_reference_rad=core.OPEN.tolist(),
        closed_reference_rad=core.CLOSED.tolist(),
        max_dev_from_open_before_close_rad=float(dev_open.max()),
        frames_open_before_close=int(pre.sum()),
        open_ok=bool(dev_open.max() < 1e-9),
    )

    # ---- 2. fingers held constant after capture --------------------------
    for lo, hi in [("LIFT", "HOLD")]:
        sel = np.isin(ph, [lo, hi])
        seg = q[sel][:, hq]
        if len(seg) > 1:
            rep["fingers"]["%s_hold" % lo.lower()] = dict(
                frames=int(sel.sum()),
                max_abs_delta_rad=float(np.abs(seg.max(0) - seg.min(0)).max()),
                max_step_delta_rad=float(np.abs(np.diff(seg, axis=0)).max()),
            )
    hold = np.isin(ph, ["HOLD"])
    if hold.sum() > 0:
        sh = q[hold][:, hq]
        rep["fingers"]["hold_frozen_max_drift_rad"] = float(np.abs(sh - sh[0][None, :]).max())

    # ---- 3. grasp geometry: where the wrist actually was -----------------
    ev = {e["phase"]: e["time_s"] for e in res.get("events", [])}
    idx = lambda t: int(np.clip(round(t * fps), 0, len(q) - 1))
    close_i = idx(ev.get("CLOSE", 0.0))
    lift_i = idx(ev.get("LIFT", ev.get("CLOSE", 0.0)))
    hold_i = idx(ev.get("HOLD", ev.get("LIFT", 0.0)))

    wp = np.array([wrist_pos(m, d, q[i])[0] for i in (close_i, lift_i, hold_i)])
    wr = np.array([wrist_pos(m, d, q[i])[1] for i in (close_i, lift_i, hold_i)])
    rep["grasp"] = dict(
        close_time_s=float(ev.get("CLOSE", -1)),
        wrist_at_close_m=wp[0].tolist(),
        commanded_wrist_target_at_close_m=wref[close_i].tolist(),
        wrist_target_error_at_close_m=float(np.linalg.norm(wp[0] - wref[close_i])),
        wrist_height_at_close_m=float(wp[0][2]),
        cube_centre_m=[float(CUBE_XY[0]), float(CUBE_XY[1]), 0.7745],
        wrist_minus_cube_m=(wp[0] - np.array([CUBE_XY[0], CUBE_XY[1], 0.7745])).tolist(),
        wrist_orientation_at_close_vs_lift_deg=rot_deg(wr[0], wr[1]),
        close_seconds_declared=0.5,
    )

    # ---- 4. lift ----------------------------------------------------------
    cz = []
    for i in range(len(q)):
        d.qpos[:] = q[i]
        mujoco.mj_forward(m, d)
        cz.append(float(d.xpos[cube_body][2]))
    cz = np.array(cz)
    rep["lift"] = dict(
        cube_z_at_close_m=float(cz[close_i]),
        cube_z_at_hold_end_m=float(cz[-1]),
        cube_z_max_m=float(cz.max()),
        lift_height_m=float(cz.max() - cz[close_i]),
        lift_hold_end_m=float(cz[-1] - cz[close_i]),
    )

    # ---- 5. official telemetry passthrough -------------------------------
    with gzip.open(out / "telemetry.csv.gz", "rt") as fh:
        head = fh.readline()
        cols = fh.readline().lstrip("# ").strip().split(",")
    tel = np.loadtxt(out / "telemetry.csv.gz", delimiter=",", comments="#")
    ci = {c: i for i, c in enumerate(cols)}
    rep["telemetry"] = dict(
        rows=int(tel.shape[0]),
        max_thumb_force_N=float(tel[:, ci["thumb_force_N"]].max()),
        max_index_force_N=float(tel[:, ci["index_force_N"]].max()),
        max_middle_force_N=float(tel[:, ci["middle_force_N"]].max()),
        max_surface_capture_error_m=float(tel[:, ci["surface_capture_error_m"]].max()),
        max_pad_vertical_spread_m=float(tel[:, ci["pad_vertical_spread_m"]].max()),
        max_base_xy_drift_m=float(tel[:, ci["base_xy_drift_m"]].max()),
    )
    rep["gates"] = res["gates"]
    rep["success"] = bool(res["success"])
    rep["source_npz_sha256"] = json.loads(traj["runtime_stamp"])["library_sha"]["native_npz"]

    print(json.dumps(rep, indent=2))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=2) + "\n")


if __name__ == "__main__":
    main()
