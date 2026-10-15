#!/usr/bin/env python3
"""Check a 36-column qpos CSV for wrap artefacts. Usage: chk_csv.py <csv> [...]"""
import sys
import numpy as np

for f in sys.argv[1:]:
    a = np.loadtxt(f, delimiter=",")
    j = a[:, 7:36]
    d = np.abs(np.diff(j, axis=0))
    big = [(k, round(float(d[:, k].max()), 2)) for k in range(29) if d[:, k].max() > 1.0]
    over = int(np.count_nonzero(np.abs(j) > 3.2))
    print("%-22s T=%3d cols=%d wraps>1rad:%s over3.2:%d" % (f.split("/")[-1], a.shape[0], a.shape[1], big, over))
    print("     right-arm travel:", [round(float(j[:, k].max() - j[:, k].min()), 2) for k in range(22, 29)])
    print("     right-arm per-step max:", [round(float(d[:, k].max()), 3) for k in range(22, 29)])
