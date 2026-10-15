#!/usr/bin/env python3
"""x05eval controls on the generated-motion path: C2 (grip OFF, 3 random cells)
and C1 (determinism, 2 random cells rerun). Cell choice is random but seeded so
the pick is reproducible; the seed and the draw are printed and recorded."""
import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, "/data/group4/20261006-055934-qoder-x05eval/scripts")
import x05_driver as X  # noqa: E402

D = Path("/data/group4/20261006-055934-qoder-x05eval")
RNG_SEED = 20261006

rows = []
ok = []
for which in ("x01", "x04"):
    t = D / ("table_%s.csv" % which)
    if not t.is_file():
        continue
    for r in csv.DictReader(open(t)):
        if r.get("control_mode") == "generated-motion":
            ok.append(r)
print("[POOL] cells that actually entered generated-motion: %d" % len(ok))
rng = random.Random(RNG_SEED)
c2_pick = rng.sample(ok, 3)
c1_pick = rng.sample(ok, 2)
print("[PICK] C2 =", [r["tag"] for r in c2_pick])
print("[PICK] C1 =", [r["tag"] for r in c1_pick])

recs = []
for r in c2_pick:
    cell = json.load(open(D / "runs" / r["tag"] / "cell_result.json"))
    n = X.evaluate_cell(r["tag"], Path(cell["input_csv"]), cell["source"],
                        cell["source_fps"], cell["duration_s"], cell["meta"],
                        no_grip=True)
    recs.append(n)
    print("[C2-OFF] %s rc=%s ctrl=%s ncb=%s fn=%s lift_tail1s=%s result=%s" %
          (n["tag"], n["rc"], n.get("control_mode"), n.get("n_contact_bodies"),
           n.get("force_normal_N"), n.get("lift_sustained_tail1s_min_m"),
           (n.get("result_line") or "")[:170]), flush=True)

for r in c1_pick:
    cell = json.load(open(D / "runs" / r["tag"] / "cell_result.json"))
    n = X.evaluate_cell(r["tag"], Path(cell["input_csv"]), cell["source"],
                        cell["source_fps"], cell["duration_s"], cell["meta"],
                        index=2)
    recs.append(n)
    orig = cell
    same = all(str(orig.get(k)) == str(n.get(k)) for k in X.METRIC_KEYS)
    print("[C1-RERUN] %s tag=%s all_metrics_identical=%s" %
          (r["tag"], n["tag"], same), flush=True)
    n["c1_identical_to_first_run"] = bool(same)
    n["c1_diff_keys"] = [k for k in X.METRIC_KEYS
                         if str(orig.get(k)) != str(n.get(k))]
    (D / "runs" / n["tag"] / "cell_result.json").write_text(
        json.dumps(n, indent=2, default=str))

(D / "runs/_controls_generated.json").write_text(json.dumps(
    {"rng_seed": RNG_SEED, "c2_pick": [r["tag"] for r in c2_pick],
     "c1_pick": [r["tag"] for r in c1_pick], "records": recs}, indent=2,
    default=str))
print("[DONE] %d control runs" % len(recs))
