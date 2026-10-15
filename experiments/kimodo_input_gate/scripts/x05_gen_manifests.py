#!/usr/bin/env python3
"""Build prompt_divergence.py input manifests (run_id,prompt_id,seed,cfg_text,
csv_path,prompt_text,constraints_sha,baseline) from each worker's gen_manifest.
Subsets are split by constraint arm / cfg so that exactly ONE baseline row per
seed exists inside each subset (the tool flags >1 as ambiguous_baseline)."""
import csv
import os
import re
from pathlib import Path

OUT = Path("/data/group4/20261006-055934-qoder-x05eval/gen")
OUT.mkdir(parents=True, exist_ok=True)

BATCHES = {
    "x06": Path("/data/group4/20261006-055932-qoder-x06canon"),
    "x01": Path("/data/group4/20261006-042504-qoder-x01gen"),
    "x04": Path("/data/group4/20261006-045000-qoder-x04kimodo"),
}


def find_csv(root, cell_id):
    for c in (root / "gen" / (cell_id + ".csv"), root / (cell_id + ".csv")):
        if c.is_file():
            return c
    return None


def rows_for(batch):
    root = BATCHES[batch]
    p = root / "gen_manifest.csv"
    if not p.is_file():
        return []
    out = []
    for r in csv.DictReader(open(p)):
        cid = r["cell_id"]
        cp = find_csv(root, cid)
        if cp is None:
            continue
        out.append({
            "run_id": batch + ":" + cid,
            "prompt_id": r.get("prompt_id", ""),
            "seed": r.get("seed", ""),
            "cfg_text": r.get("cfg_text", ""),
            "cfg_constr": r.get("cfg_constr", ""),
            "arm": r.get("arm", ""),
            "csv_path": str(cp),
            "prompt_text": r.get("prompt_text", ""),
            "constraints_sha": r.get("constraint_sha256", ""),
            "loader": r.get("loader", ""),
            "lim": r.get("lim_cells_beyond_tol", ""),
        })
    return out


COLS = ["run_id", "prompt_id", "seed", "cfg_text", "csv_path", "prompt_text",
        "constraints_sha", "baseline"]


def write_subset(name, rows, baseline_prompt="P0"):
    # exactly one baseline per seed: P0 rows, excluding rerun/variant cells
    for r in rows:
        is_re = bool(re.search(r"(c1_|_rep\d|dur\d|mdtype|_ds|DS\d)", r["run_id"]))
        r["baseline"] = "1" if (r["prompt_id"] == baseline_prompt and not is_re) else "0"
    p = OUT / (name + ".csv")
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    nb = sum(1 for r in rows if r["baseline"] == "1")
    print("[SUBSET] %-22s n=%-3d baselines=%d -> %s" % (name, len(rows), nb, p))


allrows = {b: rows_for(b) for b in BATCHES}
x06 = allrows["x06"]
# canonical C arm, cfg_text=2.0  -> the 21-cell main set (7 prompt x 3 seed)
write_subset("x06_canon_C_main",
             [r for r in x06 if r["arm"] == "C" and r["cfg_text"] == "2.0"
              and r["run_id"].split(":")[1].startswith("c2_p")])
# canonical U arm (no constraint), seed 0
write_subset("x06_canon_U_arm",
             [r for r in x06 if r["arm"] == "U"])
# text ablation cfg_text=0.0
write_subset("x06_canon_cfg0",
             [r for r in x06 if r["cfg_text"] == "0.0"])
# whole x06 in one file (baseline = the C/P0/seed... ambiguous, so no baseline)
for r in x06:
    r["baseline"] = "0"
p = OUT / "x06_all.csv"
with open(p, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=COLS, extrasaction="ignore")
    w.writeheader()
    for r in x06:
        w.writerow(r)
print("[SUBSET] x06_all (no baseline) n=%d -> %s" % (len(x06), p))

x01 = allrows["x01"]
write_subset("x01_C_main", [r for r in x01
                            if r["run_id"].split(":")[1].startswith("m0_")])
write_subset("x01_M1_armU", [r for r in x01
                             if r["run_id"].split(":")[1].startswith("m1_")])
x04 = allrows["x04"]
write_subset("x04_C_main", [r for r in x04
                            if r["run_id"].split(":")[1].startswith("K_M0_")])
