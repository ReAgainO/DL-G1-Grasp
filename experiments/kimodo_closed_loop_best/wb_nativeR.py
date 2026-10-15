"""Check whether the harness would even see a difference if lowR/highR were taken
from the clip.

sonic_grasp.py:236 (the pinch_geometry branch) does
    lowR = d.xmat[wrist]   # wrist rotation at t=0 of the rollout
    highR = lowR
i.e. the clip's wrist pose is discarded. Line 222 (native_geometry branch) instead
uses native_R[native_frame], where
    native_frame = argmax(native_curve[:,0])
    native_curve[i] = wrist pos when the model is driven by clip frame i

This script reproduces native_curve / native_R for both the delivered p6 clip and
the new natural n4 clip and reports:
  - native_frame for each
  - the rotation difference between the two clips at their respective native_frame
    (as a geodesic angle in degrees)
If that angle is large, swapping the source is meaningful.
"""
import numpy as np
import os
import sys

B = "/data/group4/20261008-232029-workbuddy-34e89f61"
R = os.path.join(B, "harness_s1000", "rep")
sys.path.insert(0, R)
import mujoco  # noqa: E402

CONV = os.path.join(B, "kimodo_conv")


def clip_curve(stem):
    """Load a converted 36-col clip and drive the model to get wrist pos/rot."""
    csv = os.path.join(CONV, stem + ".csv")
    a = np.loadtxt(csv, delimiter=",", ndmin=2)
    return a


def compute(stem, scene):
    m = mujoco.MjModel.from_xml_path(scene)
    d = mujoco.MjData(m)
    geo = mujoco.MjData(m)
    # reset to the scene's keyframe / initial state
    mujoco.mj_forward(m, d)
    a = clip_curve(stem)

    # the controller arm indices: find wrist body and the 7 arm joints
    wrist = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "right_wrist_yaw_link")

    curve = []
    Rlist = []
    for i in range(a.shape[0]):
        geo.qpos[:] = d.qpos
        geo.qpos[:3] = [0, 0, .74]
        geo.qpos[3:7] = [1, 0, 0, 0]
        # the clip's 29 body joints map to qpos[7:36]
        geo.qpos[7:36] = a[i, 7:36]
        mujoco.mj_forward(m, geo)
        curve.append(geo.xpos[wrist].copy())
        Rlist.append(geo.xmat[wrist].reshape(3, 3).copy())
    curve = np.asarray(curve)
    Rlist = np.asarray(Rlist)
    return curve, Rlist


def geodesic_deg(Ra, Rb):
    R = Ra.T @ Rb
    c = (np.trace(R) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))))


scene = os.path.join(R, "out", "wb_kimo_p6l1", "scene.xml")
res = {}
for stem in ["p6_conv", "n4_conv"]:
    curve, Rl = compute(stem, scene)
    nf = int(np.argmax(curve[:, 0]))
    res[stem] = (curve, Rl, nf)
    print("%-9s frames=%-4d native_frame=%d  wrist_x@nf=%.4f  wrist_z@nf=%.4f" %
          (stem, curve.shape[0], nf, curve[nf, 0], curve[nf, 2]))

print()
c6, R6, nf6 = res["p6_conv"]
c4, R4, nf4 = res["n4_conv"]

# compare the two clips' wrist rotation at the SAME frame index and at each
# clip's own native_frame
print("rotation difference between p6 and n4 clips (geodesic, deg):")
for i in [0, 20, 34, 40, 50, 60, min(nf6, c4.shape[0] - 1)]:
    if i < len(R6) and i < len(R4):
        print("   frame %-3d  |dR| = %7.2f deg" % (i, geodesic_deg(R6[i], R4[i])))

print()
print("at each clip's own native_frame (p6 nf=%d, n4 nf=%d):" % (nf6, nf4))
print("   |R6[nf6] - R6[nf6]| = 0 (reference)")
print("   |R4[nf4] - R6[nf6]| = %.2f deg  <-- the rotation change if we swap source"
      % geodesic_deg(R6[nf6], R4[nf4]))
