"""ws1 report: aggregate out/runs/*.json into success_table.csv + summary.json."""
import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1_lib as L

COLS = ["tag", "edge_mm", "mode", "seed", "hand_kp_override", "success", "fail_reason",
        "lift_final_m", "lift_max_m", "slip_m", "contact_any_lift", "contact_frac_lift",
        "fi_max_N", "spawn_clearance_m", "lam_touch", "lam_g", "release_slip_m",
        "release_drop_m", "weld_free", "weld_active_end", "mujoco_version", "model_sha"]


def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(L.RUNS_DIR, "*.json"))):
        name = os.path.basename(p)
        if name.endswith("_runtime_stamp.json"):
            continue
        tag = name[:-5]
        if not re.match(r"^e\d\d_(grasp|negctl|ideal)_\d+(_kp100)?$", tag):
            continue
        j = json.load(open(p))
        rows.append({
            "tag": tag, "edge_mm": j["edge_mm"], "mode": j["mode"], "seed": j["seed"],
            "hand_kp_override": j.get("hand_kp_override"),
            "success": j["success"], "fail_reason": j.get("fail_reason"),
            "lift_final_m": j.get("lift_final_m"), "lift_max_m": j.get("lift_max_m"),
            "slip_m": j.get("slip_m"), "contact_any_lift": j.get("contact_any_lift"),
            "contact_frac_lift": j.get("contact_frac_lift"), "fi_max_N": j.get("fi_max_N"),
            "spawn_clearance_m": j.get("spawn_clearance_m"),
            "lam_touch": j.get("lam_touch"), "lam_g": j.get("lam_g"),
            "release_slip_m": j.get("release_slip_m"), "release_drop_m": j.get("release_drop_m"),
            "weld_free": j.get("weld_free"),
            "weld_active_end": (j.get("weld_fixture") or {}).get("active_at_end"),
            "mujoco_version": (j.get("runtime_stamp") or {}).get("mujoco_version"),
            "model_sha": (j.get("runtime_stamp") or {}).get("model_sha"),
        })
    rows.sort(key=lambda r: (r["edge_mm"], r["mode"], r["seed"]))
    out_csv = os.path.join(L.ROOT, "success_table.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    # summary
    summary = {}
    for r in rows:
        key = "e%02d_%s_kp%s" % (r["edge_mm"], r["mode"], r["hand_kp_override"] or "asset")
        s = summary.setdefault(key, {"n": 0, "success": 0, "lift_gt_10cm": 0,
                                     "slip_lt_5mm": 0, "contact_any": 0, "weld_free": 0})
        s["n"] += 1
        s["success"] += int(bool(r["success"]))
        s["lift_gt_10cm"] += int((r["lift_final_m"] or -9) >= 0.10)
        s["slip_lt_5mm"] += int((r["slip_m"] or 9) < 0.005)
        s["contact_any"] += int(bool(r["contact_any_lift"]))
        s["weld_free"] += int(bool(r["weld_free"]))
    L.jdump(summary, os.path.join(L.OUT, "summary.json"))
    print("wrote", out_csv, "rows", len(rows))
    for k, v in sorted(summary.items()):
        print("  %-22s n=%2d success=%d lift=%d slip=%d contact=%d weldfree=%d" % (
            k, v["n"], v["success"], v["lift_gt_10cm"], v["slip_lt_5mm"],
            v["contact_any"], v["weld_free"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
