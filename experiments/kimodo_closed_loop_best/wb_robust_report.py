"""Summarize the Kimodo robustness sweep: success rate over all Kimodo cells.

Reads every result.json under harness_s1000/rep/out/ and classifies cells by
whether the approach (reach) clip came from Kimodo or from the official baseline.

Classification is data-driven from result.json["source"]["source_npz"], not from
the cell name, so it cannot be fooled by naming.

Outputs a machine-readable JSON next to this script and prints a human table.
"""
import json
import glob
import os

D = "/data/group4/20261008-232029-workbuddy-34e89f61"
B = os.path.join(D, "harness_s1000", "rep", "out")

OFFICIAL_REACH_STEMS = {"near_s42", "control_s42", "far_s42",
                        "new_motion_cube_a_s42", "reach_s43_v2",
                        "kimo_reach_s43"}
OFFICIAL_LIFT_STEMS = {"lift_s42_v2", "lift_s7_v2"}


def classify(src_npz_path):
    """Return 'kimodo' or 'official' for the reach clip of a cell."""
    if not src_npz_path:
        return "unknown"
    stem = os.path.basename(src_npz_path)
    if stem.endswith(".npz"):
        stem = stem[:-4]
    if stem in OFFICIAL_REACH_STEMS:
        return "official"
    if stem.startswith("p") and stem[1:].split("_")[0].isdigit():
        return "kimodo"
    return "other:" + stem


cells = []
for d in sorted(glob.glob(B + "/wb_*")):
    name = os.path.basename(d)
    f = os.path.join(d, "result.json")
    rec = {"cell": name, "have_result": os.path.exists(f)}
    if rec["have_result"]:
        r = json.load(open(f))
        gates = r.get("gates", {}) or {}
        src = r.get("source", {}) or {}
        rec.update({
            "success": bool(r.get("success")),
            "gates_pass": sum(1 for v in gates.values() if v),
            "gates_total": len(gates),
            "failed_gates": [k for k, v in gates.items() if not v],
            "max_lift_m": r.get("max_lift_m"),
            "hold_min_lift_m": r.get("hold_min_lift_m"),
            "hold_min_contact_bodies": r.get("hold_min_contact_bodies"),
            "robot_table_all_max_normal_N":
                (r.get("balance_audit_summary") or {}).get("robot_table_all_max_normal_N"),
            "duration_s": r.get("duration_s"),
            "wall_s": r.get("wall_s"),
            "reach_stem": os.path.basename(src.get("source_npz", "")) .replace(".npz", "")
                if src.get("source_npz") else None,
            "reach_group": classify(src.get("source_npz")),
        })
    cells.append(rec)


def rate(rows):
    n = len(rows)
    k = sum(1 for r in rows if r.get("success"))
    return k, n, (100.0 * k / n if n else 0.0)


finished = [c for c in cells if c["have_result"]]
kim = [c for c in finished if c["reach_group"] == "kimodo"]
off = [c for c in finished if c["reach_group"] == "official"]

print("=" * 96)
print("PER-CELL RESULTS")
print("=" * 96)
print("%-16s %-7s %-8s %-10s %-9s %-8s %s" %
      ("cell", "succ", "gates", "lift_m", "tbl_N", "rch", "failed gates"))
print("-" * 96)
for c in cells:
    if not c["have_result"]:
        print("%-16s %s" % (c["cell"], "-- NO result.json (did not finish)"))
        continue
    lv = c["max_lift_m"]
    lv = ("%.5f" % lv) if isinstance(lv, float) else str(lv)
    tn = c["robot_table_all_max_normal_N"]
    tn = ("%.4f" % tn) if isinstance(tn, float) else str(tn)
    print("%-16s %-7s %-8s %-10s %-9s %-8s %s" %
          (c["cell"], str(c["success"]), "%d/%d" % (c["gates_pass"], c["gates_total"]),
           lv, tn, c["reach_stem"], c["failed_gates"]))

print()
print("=" * 96)
print("SUCCESS RATE — KIMODO-REACH CELLS ONLY")
print("=" * 96)
k, n, p = rate(kim)
print("  finished Kimodo-reach cells : %d" % n)
print("  success=True                : %d" % k)
print("  RAW SUCCESS RATE            : %.1f%%" % p)
print()
print("  per-cell:")
for c in kim:
    print("    %-16s success=%-6s gates=%d/%d reach=%s lift=%.5f m" %
          (c["cell"], c["success"], c["gates_pass"], c["gates_total"],
           c["reach_stem"], c["max_lift_m"] or 0.0))

print()
print("=" * 96)
print("SUCCESS RATE — OFFICIAL-REACH CELLS (non-Kimodo baseline)")
print("=" * 96)
k2, n2, p2 = rate(off)
print("  finished official-reach cells : %d   success=%d   rate=%.1f%%" % (n2, k2, p2))

print()
print("=" * 96)
print("ALL FINISHED CELLS")
print("=" * 96)
k3, n3, p3 = rate(finished)
print("  finished=%d  success=%d  rate=%.1f%%" % (n3, k3, p3))

out = {
    "cells": cells,
    "kimodo_reach": {"finished": n, "success": k, "rate_pct": p,
                     "cells": [c["cell"] for c in kim]},
    "official_reach": {"finished": n2, "success": k2, "rate_pct": p2,
                       "cells": [c["cell"] for c in off]},
    "all_finished": {"finished": n3, "success": k3, "rate_pct": p3},
}
dst = os.path.join(D, "robust_sweep_summary.json")
with open(dst, "w") as fh:
    json.dump(out, fh, indent=2)
print()
print("wrote", dst)
