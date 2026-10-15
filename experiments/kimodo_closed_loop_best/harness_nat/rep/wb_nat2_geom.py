#!/usr/bin/env python3
"""NAT-EXP 2 geometry diagnostic.

The treatment (--pinch-native-orientation) recomputes grasp/highpos from the
clip's wrist orientation.  Question: how far does that move the approach target,
and does the wrist still clear clearance_z=0.90 m in time?

This re-derives, for both orientation modes, the values the harness computes at
sonic_grasp.py:239-249:
    offset      = wrist - cube          (t=0, closed hand)
    lowR/highR  = t=0 wrist rot  OR  native_R[native_frame]
    grasp       = cube + lowR@offset
    highpos     = grasp + [0,0,0.10]

Run:  cd harness_nat/rep && MUJOCO_GL=disable PYTHONPATH=. python wb_nat2_geom.py <stem>
"""
import os
import sys

import numpy as np
import mujoco

R = "/data/group4/20261008-232029-workbuddy-34e89f61/harness_nat/rep"
STAND_INIT_HEIGHT = 0.788740
TABLE_TOP_Z = 0.725
CUBE = np.array([0.267, -0.118, 0.7745])
NEUTRAL = None

stem = sys.argv[1] if len(sys.argv) > 1 else "p6_conv"


def build_scene():
    """Reuse the harness's own scene builder via its scene_and_cal."""
    import sonic_grasp as sg
    from pathlib import Path
    root = Path(R)
    out = root / "out" / ("_geom_probe_" + os.environ.get("GPROBE", "a"))
    if out.exists():
        import shutil
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    scene, offset, lowR0, highpos0, highR0 = sg.scene_and_cal(
        root, out, False, True, False, False, 0.23, 35.0, 0.267, -0.118)
    return Path(scene), offset


def main():
    scene_path, offset = build_scene()
    m = mujoco.MjModel.from_xml_path(str(scene_path))
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)

    wrist = m.body("right_wrist_yaw_link").id
    cube = m.body("red_cube").id
    initial_cube = d.xpos[cube].copy()
    lowR_t0 = d.xmat[wrist].reshape(3, 3).copy()

    # rebuild native_R from the clip exactly as the harness does (lines 210-214)
    import sonic_grasp as sg
    from pathlib import Path
    npz = Path(R) / "src" / "original_motions" / (stem + ".npz")
    motion = sg.ArdyMotion(npz, check_csv=Path(R) / "src" / "original_motions" / (stem + ".csv"))
    controller_aq = None
    geo = mujoco.MjData(m)
    # the harness indexes geo.qpos[controller.aq] (29 actuator joints), not [7:]
    import sonic_grasp as sg2
    ctrl = sg2.s.SonicV11(m)
    aq = ctrl.aq
    curve, natR = [], []
    for i in range(len(motion.qpos)):
        geo.qpos[:] = d.qpos
        geo.qpos[:3] = [0, 0, .74]
        geo.qpos[3:7] = [1, 0, 0, 0]
        geo.qpos[aq] = motion.qpos[i, 7:]
        mujoco.mj_forward(m, geo)
        curve.append(geo.xpos[wrist].copy())
        natR.append(geo.xmat[wrist].reshape(3, 3).copy())
    curve = np.asarray(curve)
    natR = np.asarray(natR)
    nf = int(np.argmax(curve[:, 0]))

    print(f"stem={stem}  frames={len(motion.qpos)}  native_frame={nf}")
    print(f"  initial cube          {np.round(initial_cube,4)}")
    print(f"  offset (wrist-cube)   {np.round(offset,4)}")
    print(f"  wrist t=0 pos         {np.round(d.xpos[wrist],4)}")
    print(f"  native wrist @nf      {np.round(curve[nf],4)}")

    # rotation difference between the two candidate orientations
    Rd = lowR_t0.T @ natR[nf]
    ang = np.degrees(np.arccos(np.clip((np.trace(Rd) - 1) / 2, -1, 1)))
    print(f"  geodesic diff t0 vs native_R[nf] : {ang:.2f} deg")

    for tag, RR in (("t0 (control)", lowR_t0), ("native (treat)", natR[nf])):
        lo = RR.T @ offset
        grasp = initial_cube + RR @ lo
        highpos = grasp + np.array([0, 0, .10])
        print(f"  [{tag:14s}] grasp={np.round(grasp,4)} highpos={np.round(highpos,4)} "
              f"highpos_z={highpos[2]:.4f}  clearance_z_req=0.90")


if __name__ == "__main__":
    main()
