"""Fork placement.json rows into standalone variant placement files.

usage: python ws1_variants.py
Writes out/probe/placement_var_<edge>_<pair>_<lam>.json for chosen variants.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1_lib as L

VARIANTS = [
    (20, "ti", 0.180), (20, "ti", 0.218), (20, "tm", 0.502), (20, "tm", 0.602),
    (25, "ti", 0.170), (25, "ti", 0.207), (25, "tm", 0.478), (25, "tm", 0.579),
    (35, "ti", 0.099), (35, "ti", 0.136),
]


def main():
    pl = L.jload(os.path.join(L.PROBE_DIR, "placement.json"))
    for edge, pair, lam in VARIANTS:
        rows = pl["sizes"][str(edge)]["rows"]
        cand = [r for r in rows if r["pair"] == pair]
        if not cand:
            print("no rows for", edge, pair)
            continue
        best = min(cand, key=lambda r: abs(r["lam"] - lam))
        out = dict(pl)
        out["sizes"] = dict(pl["sizes"])
        out["sizes"][str(edge)] = dict(pl["sizes"][str(edge)])
        out["sizes"][str(edge)]["chosen"] = best
        name = "placement_var_%d_%s_%03d.json" % (edge, pair, int(round(best["lam"] * 1000)))
        L.jdump(out, os.path.join(L.PROBE_DIR, name))
        print("wrote", name, "lam=%.3f clr0=%.4f pinch=%.4f/%.4f third=%.4f" % (
            best["lam"], best["clr0"], best["pinch_a"], best["pinch_b"], best["third"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
