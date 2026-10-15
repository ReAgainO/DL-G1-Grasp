"""ws1b diagnostics: replicate the runner start-up and log why pads do/don't reach the cube.

Logs every 50 steps (dt=0.002): t, base z, shoulder pitch qpos, finger joint qpos
(converted to closure lambda via O7/T7), min pad-cube distance (mj_geomDistance,
pads only), number of contacts (any), pad-cube contacts, and ctrl lambda.
Phases (steps): settle 250, close 400, hold 400, lift 500, hold 500.
"""
import argparse
import os
import sys

import numpy as np

import mujoco

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1b_lib as L

LIFT = 0.15
T_SETTLE, T_CLOSE, T_HOLD, T_LIFT, T_HOLDL = 0.5, 0.8, 0.8, 1.0, 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge", type=int, default=20)
    ap.add_argument("--placement", required=True)
    ap.add_argument("--scene", default=None)
    ap.add_argument("--lam-extra", type=float, default=0.06)
    ap.add_argument("--steps", type=int, default=1100)
    args = ap.parse_args()

    pl = L.jload(args.placement)
    sspec = pl["sizes"][str(args.edge)]
    chosen = sspec["chosen"]
    armv, O7, T7 = pl["arm_vals"], np.array(pl["O7"]), np.array(pl["T7"])
    P0 = np.array(chosen["P"])
    scene = args.scene or os.path.join(L.MODEL_DIR, "ws1b_scene_%dmm.xml" % args.edge)
    m = mujoco.MjModel.from_xml_path(scene)
    d = mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m, d, 0)
    dt = m.opt.timestep
    pads = L.pad_ids(m)

    def jid(n):
        return mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)

    def aid(n):
        return mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n)

    cubj = jid("cube_free")
    ca = m.jnt_qposadr[cubj]
    cube_g = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "cube_geom")
    wid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_EQUALITY, "cube_holder")
    ha = {n: m.jnt_qposadr[jid(n)] for n in L.RH_JOINTS}
    ft = np.zeros(6)
    for n, v in zip(L.RIGHT_ARM_JOINTS, armv):
        d.qpos[m.jnt_qposadr[jid(n)]] = v
        d.ctrl[aid(n)] = v
    for i, n in enumerate(L.RH_JOINTS):
        d.qpos[ha[n]] = O7[i]
        d.ctrl[aid(n)] = O7[i]
    d.qpos[ca:ca + 3] = P0
    d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]
    d.eq_active[wid] = 1
    base0 = float(d.qpos[2])
    mujoco.mj_forward(m, d)
    # settle the arm under gravity (fingers open), same probe as ws1b_run.py
    for _ in range(650):
        mujoco.mj_step(m, d)
    base_qpos = d.qpos.copy()
    mujoco.mj_forward(m, d)

    n1, n2, n3 = int(T_SETTLE / dt), int(T_CLOSE / dt), int(T_HOLD / dt)
    lam_touch = None
    for lam in np.arange(0.0, 0.951, 0.01):
        cq = d.qpos[ca:ca + 7].copy()
        d.qpos[:] = base_qpos
        d.qpos[ca:ca + 7] = cq
        for i, n in enumerate(L.RH_JOINTS):
            d.qpos[ha[n]] = O7[i] + lam * (T7[i] - O7[i])
        mujoco.mj_kinematics(m, d)
        mujoco.mj_comPos(m, d)
        if min(mujoco.mj_geomDistance(m, d, cube_g, g, 0.3, ft) for g in pads.values()) <= 0.0005:
            lam_touch = float(lam)
            break
    lam_g = min(0.985, (lam_touch if lam_touch is not None else 0.5) + args.lam_extra)
    print("static: lam_touch=%s lam_g=%.3f base0=%.4f cube P=%s" % (lam_touch, lam_g, base0, P0))

    # reset to the same state (the sweep moved qpos)
    mujoco.mj_resetDataKeyframe(m, d, 0)
    for n, v in zip(L.RIGHT_ARM_JOINTS, armv):
        d.qpos[m.jnt_qposadr[jid(n)]] = v
        d.ctrl[aid(n)] = v
    for i, n in enumerate(L.RH_JOINTS):
        d.qpos[ha[n]] = O7[i]
        d.ctrl[aid(n)] = O7[i]
    d.qpos[ca:ca + 3] = P0
    d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]
    d.eq_active[wid] = 1
    mujoco.mj_forward(m, d)

    def lam_of_fingers():
        lams = []
        for i, n in enumerate(L.RH_JOINTS):
            den = (T7[i] - O7[i])
            if abs(den) > 1e-6:
                lams.append((d.qpos[ha[n]] - O7[i]) / den)
        return float(np.mean(lams))

    def min_pad():
        return min(mujoco.mj_geomDistance(m, d, cube_g, g, 0.3, ft) for g in pads.values())

    sh_j = m.jnt_qposadr[jid("right_shoulder_pitch_joint")]
    for k in range(args.steps):
        if k < n1:
            pass
        elif k < n1 + n2:
            frac = (k - n1) / max(1, n2 - 1)
            for i, n in enumerate(L.RH_JOINTS):
                d.ctrl[aid(n)] = O7[i] + frac * lam_g * (T7[i] - O7[i])
        elif k < n1 + n2 + n3:
            if k == n1 + n2:
                d.eq_active[wid] = 0
        elif k < n1 + n2 + n3 + int(T_LIFT / dt):
            d.qpos[2] += LIFT * dt / T_LIFT
        else:
            d.qpos[2] = base0 + LIFT
        mujoco.mj_step(m, d)
        if k % 50 == 0 or k in (n1 + n2 - 1, n1 + n2 + n3 - 1):
            ncc = 0
            for ci in range(d.ncon):
                con = d.contact[ci]
                if cube_g in (con.geom1, con.geom2):
                    ncc += 1
            dist = min_pad()
            print("k=%4d t=%.2f basez=%.4f shp=%+.4f lam_actual=%+.3f lam_ctrl=%+.3f "
                  "d_pad=%+.4f ncon_cube=%d cz=%.4f"
                  % (k, d.time, d.qpos[2], d.qpos[sh_j], lam_of_fingers(),
                     min(1.0, (k - n1) / max(1, n2) * lam_g) if k >= n1 else 0.0,
                     dist, ncc, d.qpos[ca + 2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
