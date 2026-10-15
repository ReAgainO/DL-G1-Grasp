#!/usr/bin/env python3
"""Export the executed grasp action as a fixed-root CSV at 30 fps.

Source: <rep>/out/<name>/trajectory.npz written by the official
sonic_grasp.py (qpos stored every 20 physics steps = 25 Hz).

The task scenario pins the robot root, so the emitted root block is held at
exactly [0, 0, 0.7887] with the identity quaternion, and every other joint
follows the simulation's executed trajectory.

Columns:
  t_s, root_x, root_y, root_z, quat_w, quat_x, quat_y, quat_z,
  <29 body joints>, <7 left-hand joints>, <7 right-hand joints>

Usage: export_action_csv.py <trajectory.npz> <out.csv> [--fps 30] [--report out.json]
"""
import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

ROOT_FIXED = np.array([0.0, 0.0, 0.7887])
QUAT_FIXED = np.array([1.0, 0.0, 0.0, 0.0])


def resample_linear(x, fps_in, fps_out):
    """Resample (T, D) along time. Angles are unwrapped first so a joint that
    crosses +-pi is not averaged across the branch cut."""
    T = x.shape[0]
    out_T = int(round((T - 1) * fps_out / fps_in)) + 1
    src = np.arange(T) / fps_in
    dst = np.arange(out_T) / fps_out
    dst = np.clip(dst, 0.0, src[-1])
    xs = np.unwrap(x, axis=0)
    out = np.empty((out_T, x.shape[1]))
    for c in range(x.shape[1]):
        out[:, c] = np.interp(dst, src, xs[:, c])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("traj")
    ap.add_argument("out")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()

    z = np.load(a.traj, allow_pickle=True)
    q = np.asarray(z["qpos"], dtype=np.float64)          # (T, 57) at 25 Hz
    fps_in = float(z["fps"])
    scene = str(z["scene"])
    phases = [str(p) for p in z["phase"]]

    m = mujoco.MjModel.from_xml_path(scene)
    # hinge joints in qpos order
    hinges = sorted(
        [(int(m.jnt_qposadr[j]), m.joint(j).name, int(j)) for j in range(m.njnt)
         if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE],
        key=lambda r: r[0])
    body = [h for h in hinges][:29]
    left_hand = [h for h in hinges][29:36]
    right_hand = [h for h in hinges][36:43]
    assert len(hinges) == 43, "expected 29 body + 14 hand hinges, got %d" % len(hinges)

    cols = [h[0] for h in body] + [h[0] for h in left_hand] + [h[0] for h in right_hand]
    names = [h[1] for h in body] + [h[1] for h in left_hand] + [h[1] for h in right_hand]
    joints = q[:, cols]

    j_out = resample_linear(joints, fps_in, a.fps)
    T_out = j_out.shape[0]

    # root block is pinned to the scenario definition
    root = np.tile(ROOT_FIXED, (T_out, 1))
    quat = np.tile(QUAT_FIXED, (T_out, 1))
    t = np.arange(T_out) / a.fps

    table = np.column_stack([t, root, quat, j_out])
    header = (["t_s", "root_x", "root_y", "root_z", "quat_w", "quat_x", "quat_y",
               "quat_z"] + names)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        fh.write(",".join(header) + "\n")
        np.savetxt(fh, table, delimiter=",", fmt="%.9g")
    print("wrote", out, out.stat().st_size, "bytes", table.shape)

    # per-phase time boundaries on the 25 Hz source clock
    bounds = []
    for i, p in enumerate(phases):
        if not bounds or bounds[-1][0] != p:
            bounds.append([p, i / fps_in, i / fps_in])
        else:
            bounds[-1][2] = i / fps_in
    print("phases (25 Hz source clock):")
    for p, s0, s1 in bounds:
        print("   %-15s %6.3f .. %6.3f  (%.3f s)" % (p, s0, s1, s1 - s0))

    rep = dict(source=str(a.traj), fps_out=a.fps, fps_source=fps_in,
               frames=T_out, duration_s=float(T_out / a.fps),
               root_fixed=ROOT_FIXED.tolist(), quat_fixed=QUAT_FIXED.tolist(),
               columns=header, phases=[dict(phase=p, start_s=s0, end_s=s1) for p, s0, s1 in bounds])
    if a.report:
        Path(a.report).write_text(json.dumps(rep, indent=2) + "\n")
        print("wrote", a.report)


if __name__ == "__main__":
    main()
