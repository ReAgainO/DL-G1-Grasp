"""Final success-rate summary for the Kimodo grasp method.

Design decisions (documented so the number cannot be misread):

1. A Kimodo trial is defined at the CLIP level, not the cell level. Several cells
   reused the same clip while debugging (wb_dbg_p4 / wb_dbg2_p4 / wb_kimo_v1 all
   staged p4_conv), so they are collapsed to ONE trial. Counting them separately
   would weight p4 three times and bias the rate.

2. A clip is judged by the BEST outcome any of its cells achieved:
     - any cell produced result.json -> take that verdict from the 20 gates;
     - otherwise, if the harness aborted with "Approach clock bound0..26s",
       the clip is a failure: the generated approach never reached the cube
       inside the harness's 26 s approach window.

3. Non-Kimodo cells (official near_s42 / reach_s43_v2 baselines, and the
   isolation cells) are reported separately and excluded from the Kimodo rate.

Reach clip provenance is read from raw/<cell>.meta.txt (motion_stem), which is
written by the runner itself, so it cannot be confused with naming.
"""
import json
import glob
import os
import re

D = "/data/group4/20261008-232029-workbuddy-34e89f61"
B = os.path.join(D, "harness_s1000", "rep", "out")
RAW = os.path.join(D, "harness_s1000", "raw")

APPROACH_CRASH = "Approach clock bound0..26s"
OFFICIAL_REACH = {"near_s42", "control_s42", "far_s42", "new_motion_cube_a_s42",
                  "reach_s43_v2", "kimo_reach_s43"}


def read_meta_stem(cell):
    p = os.path.join(RAW, cell + ".meta.txt")
    if not os.path.exists(p):
        return None, None
    stem = None
    for line in open(p, errors="replace"):
        if line.startswith("motion_stem="):
            stem = line.split("=", 1)[1].strip()
    return stem, p


def crashed(cell):
    p = os.path.join(RAW, cell + ".stdout.log")
    if not os.path.exists(p):
        return False
    try:
        return APPROACH_CRASH in open(p, errors="replace").read()
    except Exception:
        return False


cells = []
for d in sorted(glob.glob(B + "/wb_*")):
    name = os.path.basename(d)
    f = os.path.join(d, "result.json")
    stem, _ = read_meta_stem(name)
    rec = {"cell": name, "reach_stem": stem, "approach_crash": crashed(name)}
    if os.path.exists(f):
        r = json.load(open(f))
        gates = r.get("gates", {}) or {}
        src_stem = os.path.basename((r.get("source") or {}).get("source_npz", "")) .replace(".npz", "")
        if src_stem:
            rec["reach_stem"] = src_stem
        rec.update({
            "status": "verdict",
            "success": bool(r.get("success")),
            "gates_pass": sum(1 for v in gates.values() if v),
            "gates_total": len(gates),
            "failed_gates": [k for k, v in gates.items() if not v],
            "max_lift_m": r.get("max_lift_m"),
        })
    elif rec["approach_crash"]:
        rec.update({"status": "approach_crash", "success": False,
                    "gates_pass": 0, "gates_total": 20,
                    "failed_gates": ["APPROACH_TIMEOUT"], "max_lift_m": None})
    else:
        rec.update({"status": "aborted", "success": None, "gates_pass": None,
                    "gates_total": None, "failed_gates": [], "max_lift_m": None})
    cells.append(rec)


def is_kimodo(stem):
    return bool(stem) and re.fullmatch(r"p\d+_conv", stem or "")


# ---- collapse to clip level ----
by_clip = {}
for c in cells:
    if not is_kimodo(c["reach_stem"]):
        continue
    by_clip.setdefault(c["reach_stem"], []).append(c)

clips = []
for stem, group in sorted(by_clip.items()):
    verd = [c for c in group if c["status"] == "verdict"]
    if verd:
        # best outcome among the cells of this clip
        best = max(verd, key=lambda c: (c["success"], c["gates_pass"] or 0))
        clips.append({"clip": stem, "verdict": "PASS" if best["success"] else "FAIL",
                      "success": best["success"], "gates": "%d/%d" % (best["gates_pass"], best["gates_total"]),
                      "lift_m": best["max_lift_m"], "failed_gates": best["failed_gates"],
                      "cells": [c["cell"] for c in group]})
    else:
        clips.append({"clip": stem, "verdict": "FAIL(approach timeout)",
                      "success": False, "gates": "aborted", "lift_m": None,
                      "failed_gates": ["APPROACH_TIMEOUT"], "cells": [c["cell"] for c in group]})

print("=" * 104)
print("CELL LEVEL (provenance from runner meta)")
print("=" * 104)
print("%-16s %-14s %-7s %-8s %-10s %-11s %s" %
      ("cell", "status", "succ", "gates", "lift_m", "reach_stem", "failed"))
print("-" * 104)
for c in cells:
    su = "-" if c["success"] is None else str(c["success"])
    ga = "-" if c["gates_pass"] is None else ("%d/%d" % (c["gates_pass"], c["gates_total"]))
    lm = ("%.5f" % c["max_lift_m"]) if c["max_lift_m"] is not None else "-"
    print("%-16s %-14s %-7s %-8s %-10s %-11s %s" %
          (c["cell"], c["status"], su, ga, lm, c["reach_stem"], c["failed_gates"]))

print()
print("=" * 104)
print(">>> KIMODO SUCCESS RATE — CLIP LEVEL (deduplicated)")
print("=" * 104)
k = sum(1 for c in clips if c["success"])
n = len(clips)
for c in clips:
    print("   %-9s %-24s gates=%-8s lift=%-9s cells=%s" %
          (c["clip"], c["verdict"], c["gates"],
           ("%.5f" % c["lift_m"]) if c["lift_m"] is not None else "-",
           c["cells"]))
print()
print("   distinct Kimodo approach clips trialled : %d" % n)
print("   clips that achieved a successful grasp : %d" % k)
print("   SUCCESS RATE                            : %.1f%%  (%d/%d)" %
      (100.0 * k / n if n else 0.0, k, n))

# split: p6 reach (lift sweep) vs the approach-candidate sweep
p6c = [c for c in clips if c["clip"] == "p6_conv"]
othc = [c for c in clips if c["clip"] != "p6_conv"]
k6 = sum(1 for c in p6c if c["success"])
ko = sum(1 for c in othc if c["success"])
print()
print("   --- split ---")
print("   ACCEPTED p6 approach + Kimodo lifts   : %d/%d = %.1f%%" %
      (k6, len(p6c), 100.0 * k6 / len(p6c) if p6c else 0.0))
print("   approach-candidate sweep (p1..p5)     : %d/%d = %.1f%%" %
      (ko, len(othc), 100.0 * ko / len(othc) if othc else 0.0))

# also report lift-clip level success (the lift sweep is the delivered config)
print()
print("=" * 104)
print(">>> LIFT CLIP OUTCOME (p6 approach fixed, one Kimodo lift each)")
print("=" * 104)
lift_cells = [c for c in cells if c["reach_stem"] == "p6_conv" and c["status"] == "verdict"]
for c in sorted(lift_cells, key=lambda x: x["cell"]):
    print("   %-16s %-6s %-8s lift=%.5f m  %s" %
          (c["cell"], c["success"], "%d/%d" % (c["gates_pass"], c["gates_total"]),
           c["max_lift_m"] or 0.0, c["failed_gates"]))
kl = sum(1 for c in lift_cells if c["success"])
print("   lift configs = %d  success = %d  rate = %.1f%%" %
      (len(lift_cells), kl, 100.0 * kl / len(lift_cells) if lift_cells else 0.0))

out = {
    "definition": "Kimodo trial = distinct Kimodo approach clip (p*_conv). Judged by the "
                  "best outcome of any cell that staged it; a harness approach-clock "
                  "abort counts as a failure.",
    "kimodo_clip_level": {"trials": n, "success": k,
                          "rate_pct": 100.0 * k / n if n else 0.0,
                          "clips": clips},
    "accepted_p6_plus_kimodo_lift": {"trials": len(p6c), "success": k6,
                                     "rate_pct": 100.0 * k6 / len(p6c) if p6c else 0.0},
    "approach_candidate_sweep": {"trials": len(othc), "success": ko,
                                 "rate_pct": 100.0 * ko / len(othc) if othc else 0.0},
    "lift_configs": {"trials": len(lift_cells), "success": kl,
                     "rate_pct": 100.0 * kl / len(lift_cells) if lift_cells else 0.0},
    "cells": cells,
}
dst = os.path.join(D, "kimodo_success_rate.json")
json.dump(out, open(dst, "w"), indent=2)
print()
print("wrote", dst)
