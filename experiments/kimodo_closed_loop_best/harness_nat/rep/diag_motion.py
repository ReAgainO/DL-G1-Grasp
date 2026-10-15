#!/usr/bin/env python3
"""Diagnose a harness ArdyMotion clip: wrap artefacts, travel, root range.

Usage: diag_motion.py <npz> [<npz> ...]   (run from the harness rep dir)
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion_input as mi  # noqa: E402

RIGHT_ARM = {22: "sh_pitch", 23: "sh_roll", 24: "sh_yaw", 25: "elbow",
             26: "w_roll", 27: "w_pitch", 28: "w_yaw"}

for spec in sys.argv[1:]:
    p = Path(spec)
    if "=" in spec:
        tag, spec = spec.split("=", 1)
        p = Path(spec)
    else:
        tag = p.stem
    m = mi.ArdyMotion(p, check_csv=p.with_suffix(".csv"))
    q = m.qpos                      # (T, 36) root3 + quat4 + 29 joints
    j = q[:, 7:]
    d = np.abs(np.diff(j, axis=0))
    big = [(k, float(d[:, k].max())) for k in range(29) if d[:, k].max() > 1.0]
    print("%-22s T=%3d fps=%g" % (tag, len(q), m.fps))
    print("   joint-limit-violating frames:",
          int(np.count_nonzero(np.abs(j) > 3.2)))
    print("   wrap jumps >1rad/step (joint_idx, max|d|):", big)
    print("   right-arm travel (rad):",
          [round(float(j[:, k].max() - j[:, k].min()), 3) for k in RIGHT_ARM])
    print("   right-arm per-step max|d|:",
          [round(float(d[:, k].max()), 3) for k in RIGHT_ARM])
    print("   qpos root[:,2] (up) min/max: %.4f %.4f" % (q[:, 2].min(), q[:, 2].max()))
