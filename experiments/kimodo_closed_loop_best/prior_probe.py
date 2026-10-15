#!/usr/bin/env python3
"""Reproduce the harness APPROACH arm prior and FK it.

sonic_grasp.py:356 builds  prior = motion.sample([min(times[-1], (t-2)/10)])[0][0,22:29]
where t = 2.0 + elapsed_in_APPROACH (SETTLE lasts 2 s).  clearance_approach.py:24
raises once elapsed>26, and the only exit is actual_wrist_z>=clearance_z at
elapsed>=4.  So the critical window is tau in [0.4, 2.6] s of the reach clip.

Usage: prior_probe.py <scene.xml> <clip.npz> [<clip.npz> ...]
"""
import sys
from pathlib import Path
import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion_input as mi  # noqa: E402

SCENE = sys.argv[1]
CUBE = np.array([0.267, -0.118, 0.7745])
ANCHOR = np.array([0.0, 0.0, 0.7887])

m = mujoco.MjModel.from_xml_path(SCENE)
d = mujoco.MjData(m)
mujoco.mj_forward(m, d)
tid = m.geom("table_top").id
table_top_z = float(d.geom_xpos[tid, 2] + m.geom_size[tid, 2])
clearance_z = max(0.90, table_top_z + 0.14)
WB = int(m.body("right_wrist_yaw_link").id)
print("table_top_z=%.4f  clearance_z=%.4f  (need wrist_z>=%.3f at elapsed>=4s)"
      % (table_top_z, clearance_z, clearance_z))


def fk_wrist(jrow):
    """jrow = 29 body-joint values (ArdyMotion.sample() layout)."""
    d.qpos[:] = 0.0
    d.qpos[:3] = ANCHOR
    d.qpos[3:7] = [1, 0, 0, 0]
    d.qpos[7:36] = jrow
    mujoco.mj_forward(m, d)
    return d.xpos[WB].copy()


def fk_from_36(qrow):
    return fk_wrist(qrow[7:])


for spec in sys.argv[2:]:
    p = Path(spec)
    mm = mi.ArdyMotion(p)
    tau_max = float(mm.times[-1])
    print("\n== %-18s frames=%d  times[-1]=%.4f s  (%.2f fps)"
          % (p.stem, len(mm.qpos), tau_max, 1.0 / (mm.times[1] - mm.times[0])))

    # full-clip wrist sweep, to see where the arm is genuinely high
    zs, ds = [], []
    for f in range(len(mm.qpos)):
        w = fk_from_36(mm.qpos[f])
        zs.append(w[2])
        ds.append(np.linalg.norm(w - CUBE))
    zs = np.asarray(zs); ds = np.asarray(ds)
    n = len(mm.qpos)
    print("   full clip : wrist_z %.3f..%.3f   min|cube-wrist| %.1f mm @tau=%.2f"
          % (zs.min(), zs.max(), ds.min() * 1000, mm.times[int(np.argmin(ds))]))
    for lo, hi, tag in [(0.4, 2.6, "APPROACH window")]:
        a, b = int(lo / tau_max * n), int(hi / tau_max * n)
        print("   %s tau %.1f..%.1f : wrist_z %.3f..%.3f  (>=clearance: %s)"
              % (tag, lo, hi, zs[a:b + 1].min(), zs[a:b + 1].max(),
                 bool((zs[a:b + 1] >= clearance_z).any())))

    print("   %6s %6s %8s  %s" % ("e_s", "tau", "wrist_z", "arm joints 22..28"))
    for e in [0, 2, 4, 6, 8, 10, 12, 15, 18, 21, 24, 25.9, 26.5]:
        tau = min(tau_max, e / 10.0)
        A = mm.sample(np.array([tau]))[0]
        arm = A[0, 22:29]
        w = fk_wrist(A[0])
        print("   %6.1f %6.3f %8.4f  %s" % (e, tau, w[2], np.round(arm, 3).tolist()))
