"""ws1b report: success_table.csv from out/runs/*.json + console summary."""
import argparse
import csv
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1b_lib as L

COLS = ["tag", "edge_mm", "mode", "seed", "variant", "hand_kp_override", "success",
        "fail_reason", "lift_final_m", "lift_max_m", "slip_m", "contact_any_lift",
        "contact_frac_lift", "fi_max_N", "spawn_clearance_m", "lam_touch", "lam_g",
        "release_slip_m", "release_drop_m", "weld_free", "weld_active_end",
        "sim_ok", "elapsed_s", "mujoco_version", "model_sha", "variant_model_sha",
        "pad_r", "pad_mu_override"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default="*.json")
    ap.add_argument("--out", default=os.path.join(L.ROOT, "success_table.csv"))
    args = ap.parse_args()

    rows = []
    for p in sorted(glob.glob(os.path.join(L.RUNS_DIR, args.glob))):
        if p.endswith("_runtime_stamp.json"):
            continue
        try:
            r = L.jload(p)
        except Exception as e:
            print("skip", p, e)
            continue
        st = r.get("runtime_stamp", {})
        row = {
            "tag": r.get("tag"), "edge_mm": r.get("edge_mm"), "mode": r.get("mode"),
            "seed": r.get("seed"), "variant": r.get("variant", ""),
            "hand_kp_override": r.get("hand_kp_override"),
            "success": r.get("success"), "fail_reason": r.get("fail_reason"),
            "lift_final_m": r.get("lift_final_m"), "lift_max_m": r.get("lift_max_m"),
            "slip_m": r.get("slip_m"), "contact_any_lift": r.get("contact_any_lift"),
            "contact_frac_lift": r.get("contact_frac_lift"), "fi_max_N": r.get("fi_max_N"),
            "spawn_clearance_m": r.get("spawn_clearance_m"),
            "lam_touch": r.get("lam_touch"), "lam_g": r.get("lam_g"),
            "release_slip_m": r.get("release_slip_m"), "release_drop_m": r.get("release_drop_m"),
            "weld_free": r.get("weld_free"),
            "weld_active_end": (r.get("weld_fixture") or {}).get("active_at_end"),
            "sim_ok": r.get("sim_ok"), "elapsed_s": r.get("elapsed_s"),
            "mujoco_version": st.get("mujoco_version"), "model_sha": st.get("model_sha"),
            "variant_model_sha": st.get("variant_model_sha"),
            "pad_r": st.get("pad_r"), "pad_mu_override": st.get("pad_mu_override"),
        }
        rows.append(row)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("wrote", args.out, len(rows), "rows")

    # summary: n/success per (edge, mode, arm-suffix)
    agg = {}
    for r in rows:
        tag = r["tag"]
        arm = ""
        if "grasp" in tag:
            parts = tag.split("_")
            if len(parts) >= 4:  # e20_grasp_arm_000
                arm = "_".join(parts[2:-1])
            else:
                arm = "grasp"
            key = ("grasp", r["edge_mm"], arm)
        else:
            key = (r["mode"], r["edge_mm"], "")
        a = agg.setdefault(key, [0, 0])
        a[0] += 1
        a[1] += 1 if r["success"] else 0
    for k in sorted(agg, key=lambda x: (str(x[1]), x[0])):
        print("  %-8s edge=%-4s arm=%-6s %d/%d" % (k[0], k[1], k[2], agg[k][1], agg[k][0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
