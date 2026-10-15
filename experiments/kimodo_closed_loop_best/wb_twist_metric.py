#!/usr/bin/env python
"""WB twist metric: measure wrist forearm-roll / hand-down / elbow-bend of a cell.

Usage: wb_twist_metric.py <cell_dir> [<cell_dir> ...]
Reads trajectory.npz (qpos layout: root 0:7, 43 hinges 7:50, cube free 50:57)
and reports, over the *whole* clip and per phase:
  roll_deg       total forearm roll about the world/arm axis (twist proxy)
  hand_down_deg  hand pitch away from palm-down
  elbow_deg      elbow flexion
  lift_m         cube rise from start
"""
import sys, os, json
import numpy as np

try:
    import mujoco
except Exception as e:  # pragma: no cover
    print("IMPORT_ERROR", e); sys.exit(2)

SCENE_CACHE = {}


def load_scene(cell):
    for cand in ("scene.xml", "g1_free_grasp.xml"):
        p = os.path.join(cell, cand)
        if os.path.exists(p):
            key = p
            if key not in SCENE_CACHE:
                SCENE_CACHE[key] = mujoco.MjModel.from_xml_path(p)
            return SCENE_CACHE[key]
    raise FileNotFoundError("no scene xml in " + cell)


def ang_between(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    na = np.linalg.norm(a); nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    c = float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))
    return float(np.degrees(np.arccos(c)))


def geodesic_deg(R0, R1):
    M = np.asarray(R0, float).T @ np.asarray(R1, float)
    tr = float(np.trace(M))
    return float(np.degrees(np.arccos(np.clip((tr - 1.0) / 2.0, -1.0, 1.0))))


def signed_roll_deg(R0, R1):
    """Signed rotation about the forearm long axis between two wrist frames."""
    M = np.asarray(R0, float).T @ np.asarray(R1, float)
    tr = float(np.trace(M))
    ang = float(np.arccos(np.clip((tr - 1.0) / 2.0, -1.0, 1.0)))
    if ang < 1e-9:
        return 0.0, 0.0
    ax = np.array([M[2, 1] - M[1, 2], M[0, 2] - M[2, 0], M[1, 0] - M[0, 1]])
    n = np.linalg.norm(ax)
    if n < 1e-12:
        return 0.0, 0.0
    ax = ax / n
    # project the rotation axis onto the frame's own X (forearm long axis proxy)
    share = float(abs(ax[0]))
    return float(np.degrees(ang)) * float(np.sign(ax[0]) if abs(ax[0]) > 1e-9 else 1.0), share


def analyse(cell):
    tz = os.path.join(cell, "trajectory.npz")
    if not os.path.exists(tz):
        print("MISSING", cell); return None
    z = np.load(tz, allow_pickle=True)
    qpos = z["qpos"]
    phase = z["phase"] if "phase" in z else None
    model = load_scene(cell)
    data = mujoco.MjData(model)

    def bid(n):
        i = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n)
        return i

    wrist = bid("right_wrist_yaw_link")
    elbow = bid("right_elbow_link")
    sh = bid("right_shoulder_pitch_link")
    cube = bid("cube") if bid("cube") >= 0 else bid("free_cube")

    n = qpos.shape[0]
    series = []
    for i in range(n):
        data.qpos[:] = qpos[i]
        mujoco.mj_forward(model, data)
        R = data.xmat[wrist].reshape(3, 3).copy() if wrist >= 0 else np.eye(3)
        series.append(R)
    series = np.asarray(series)

    R0 = series[0]
    # total geodesic rotation of the wrist frame start -> each frame, take max
    geo = np.array([geodesic_deg(R0, R) for R in series])
    # twist = rotation about the arm's own long axis
    tw = np.array([signed_roll_deg(R0, R)[0] for R in series])

    # cube lift
    lift = None
    if cube >= 0:
        cz = []
        for i in range(n):
            data.qpos[:] = qpos[i]
            mujoco.mj_forward(model, data)
            cz.append(data.xpos[cube][2])
        cz = np.array(cz)
        lift = float(cz.max() - cz[0])
        lift_start = float(cz[0]); lift_end = float(cz[-1])
    else:
        lift_start = lift_end = None

    res = {
        "cell": os.path.basename(cell.rstrip("/")),
        "frames": int(n),
        "total_geo_deg": float(geo.max()),
        "total_twist_deg": float(np.abs(tw).max()),
        "final_twist_deg": float(tw[-1]),
        "signed_twist_end": float(tw[-1]),
        "lift_m": lift,
        "lift_start": lift_start,
        "lift_end": lift_end,
    }
    if phase is not None:
        ph = [str(x) for x in phase]
        order = []
        for p in ph:
            if not order or order[-1] != p:
                order.append(p)
        per = {}
        for p in order:
            idx = [k for k, v in enumerate(ph) if v == p]
            if not idx:
                continue
            sub = tw[idx]
            per[p] = {
                "frames": len(idx),
                "t0": float(z["time"][idx[0]]) if "time" in z else None,
                "t1": float(z["time"][idx[-1]]) if "time" in z else None,
                "twist_span": float(np.abs(sub).max() - np.abs(sub).min()),
                "twist_absmax": float(np.abs(sub).max()),
            }
        res["phase_twist"] = per
    return res


def main():
    for c in sys.argv[1:]:
        r = analyse(c)
        if r:
            print(json.dumps(r))


if __name__ == "__main__":
    main()
