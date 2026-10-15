#!/usr/bin/env python3
"""Print raw joint-angle series for a 36-column qpos CSV around wrap points.

Usage: trace_joint.py <csv> <joint_idx> [<joint_idx> ...]
"""
import sys
import numpy as np

f = sys.argv[1]
a = np.loadtxt(f, delimiter=",")
j = a[:, 7:36]
for k in [int(x) for x in sys.argv[2:]]:
    s = j[:, k]
    d = np.abs(np.diff(s))
    w = np.argsort(d)[-3:]
    print("joint %d  min=%.3f max=%.3f  mean=%.3f" % (k, s.min(), s.max(), s.mean()))
    print("   first12:", np.round(s[:12], 3).tolist())
    print("   last12 :", np.round(s[-12:], 3).tolist())
    for t in w:
        lo = max(0, t - 2)
        print("   jump@%d: %s -> %s   |d|=%.3f"
              % (t, np.round(s[lo:t + 1], 3).tolist(), round(float(s[t + 1]), 3), d[t]))
    u = np.unwrap(s)
    du = np.abs(np.diff(u))
    print("   unwrapped: min=%.3f max=%.3f max|step|=%.4f  total_travel=%.3f"
          % (u.min(), u.max(), du.max(), u.max() - u.min()))
    print("   frames with |angle|>3.0: %d / %d" % (int((np.abs(s) > 3.0).sum()), len(s)))
