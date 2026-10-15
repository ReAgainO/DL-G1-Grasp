#!/usr/bin/env python
"""Natural-orientation gap: compare an achieved cell's APPROACH wrist orientation
against the Kimodo clip's own wrist orientation at native_frame.

Reproduces sonic_grasp.py:210-214 exactly:
  geo.qpos[:]=d.qpos; geo.qpos[:3]=[0,0,.74]; geo.qpos[3:7]=[1,0,0,0]
  geo.qpos[controller.aq]=motion.qpos[i,7:]; mj_forward
  native_curve -> xpos[wrist]; native_R -> xmat[wrist]
  native_frame = argmax(native_curve[:,0])
"""
import sys, os, json
import numpy as np
import mujoco

B = "/data/group4/20261008-232029-workbuddy-34e89f61"
H = os.path.join(B, "harness_nat2")
REP = os.path.join(H, "rep")
sys.path.insert(0, REP)
os.environ.setdefault("MUJOCO_GL", "disable")
os.environ.setdefault("N1_MOTION_STEM", "n4_conv")

import source_physics_core as core  # noqa: E402
import sonic_v11 as s  # noqa: E402
from motion_input import ArdyMotion  # noqa: E402


def geod(R0, R1):
    M = np.asarray(R0, float).T @ np.asarray(R1, float)
    tr = float(np.trace(M))
    return float(np.degrees(np.arccos(np.clip((tr - 1.0) / 2.0, -1.0, 1.0))))


def main(cells):
    stem = os.environ["N1_MOTION_STEM"]
    npz = os.path.join(REP, "src", "original_motions", stem + ".npz")
    csv = os.path.join(REP, "src", "original_motions", stem + ".csv")
    motion = ArdyMotion(npz, check_csv=csv)

    # build the model once, from the first cell's scene, to get the controller
    m = mujoco.MjModel.from_xml_path(os.path.join(cells[0], "scene.xml"))
    d = mujoco.MjData(m)
    ctrl = s.SonicV11(m)
    w = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "right_wrist_yaw_link")
    hands = np.arange(36, 43)
    hj = m.actuator_trnid[hands, 0]
    hq = m.jnt_qposadr[hj]

    # the clip's own wrist orientation
    d.qpos[:3] = [0, 0, .788740]; d.qpos[3:7] = [1, 0, 0, 0]
    d.qpos[ctrl.aq] = s.DEFAULT_ANGLES
    d.qpos[hq] = core.OPEN
    mujoco.mj_forward(m, d)
    geo = mujoco.MjData(m); geo.qpos[:] = d.qpos
    nat_curve = []; nat_R = []
    for i in range(len(motion.qpos)):
        geo.qpos[:] = d.qpos
        geo.qpos[:3] = [0, 0, .74]; geo.qpos[3:7] = [1, 0, 0, 0]
        geo.qpos[ctrl.aq] = motion.qpos[i, 7:]
        mujoco.mj_forward(m, geo)
        nat_curve.append(geo.xpos[w].copy()); nat_R.append(geo.xmat[w].reshape(3, 3).copy())
    nat_curve = np.asarray(nat_curve); nat_R = np.asarray(nat_R)
    nf = int(np.argmax(nat_curve[:, 0]))

    out = {"stem": stem, "clip_len": int(len(motion.qpos)), "native_frame": nf, "cells": {}}
    for cell in cells:
        z = np.load(os.path.join(cell, "trajectory.npz"), allow_pickle=True)
        qpos = z["qpos"]; phase = [str(p) for p in z["phase"]]
        mm = mujoco.MjModel.from_xml_path(os.path.join(cell, "scene.xml"))
        dd = mujoco.MjData(mm)
        ww = mujoco.mj_name2id(mm, mujoco.mjtObj.mjOBJ_BODY, "right_wrist_yaw_link")
        appr = [i for i, p in enumerate(phase) if p == "APPROACH"]
        a0, a1 = appr[0], appr[-1]
        R = []
        for i in (0, a0, a1):
            dd.qpos[:] = qpos[i]; mujoco.mj_forward(mm, dd)
            R.append(dd.xmat[ww].reshape(3, 3).copy())
        out["cells"][os.path.basename(cell.rstrip("/"))] = {
            "geo_appr_start_vs_native": round(geod(R[1], nat_R[nf]), 3),
            "geo_appr_end_vs_native": round(geod(R[2], nat_R[nf]), 3),
            "geo_frame0_vs_native": round(geod(R[0], nat_R[nf]), 3),
        }
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
