#!/usr/bin/env python3
"""Report, per phase, whether the servo path that consumes targetR actually runs.

We patch nothing here -- we only read the persisted artifacts (trajectory.npz
phase labels + result.json servo counters) and cross-reference the guard
conditions in sonic_grasp.py:407-424.

Usage: cd harness_nat2/rep && MUJOCO_GL=disable PYTHONPATH=. python wb_phase_gate.py <cell>
"""
import json
import os
import sys
from collections import OrderedDict

import numpy as np

R = "/data/group4/20261008-232029-workbuddy-34e89f61/harness_nat2/rep"


def main():
    cell = sys.argv[1] if len(sys.argv) > 1 else "wb_nat2_p6_off"
    # reuse the delivered tree's result if the work copy lacks it
    cands = [os.path.join(R, "out", cell),
             "/data/group4/20261008-232029-workbuddy-34e89f61/harness_s1000/rep/out/" + cell]
    d = next((c for c in cands if os.path.exists(c)), None)
    if d is None:
        print("no cell:", cell)
        return
    z = np.load(os.path.join(d, "trajectory.npz"), allow_pickle=True)
    ph = z["phase"]
    t = z["time"]
    order = OrderedDict()
    for i, p in enumerate(ph):
        p = str(p)
        if p not in order:
            order[p] = [t[i], t[i], 1]
        else:
            order[p][1] = t[i]
            order[p][2] += 1
    print(f"cell={cell}  frames={len(ph)}  fps={int(z['fps'])}")
    print(f"{'phase':<18}{'t_start':>9}{'t_end':>9}{'frames':>8}{'dur_s':>8}")
    for p, (a, b, n) in order.items():
        print(f"{p:<18}{a:>9.2f}{b:>9.2f}{n:>8}{b-a:>8.2f}")
    rj = os.path.join(d, "result.json")
    if os.path.exists(rj):
        r = json.load(open(rj))
        print()
        for k in ("servo_updates", "servo_max_delta_rad", "gates"):
            if k in r:
                v = r[k]
                if k == "gates":
                    print(f"{k}: {sum(1 for x in v.values() if x)}/{len(v)}")
                else:
                    print(f"{k}: {v}")


if __name__ == "__main__":
    main()
