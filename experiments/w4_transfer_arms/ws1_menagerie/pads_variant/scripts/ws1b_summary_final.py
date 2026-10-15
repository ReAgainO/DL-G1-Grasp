"""ws1b final aggregation: matrix tables (video runs excluded) + mechanism stats.

Emits a plain-text block used verbatim in pads_variant/RESULT.md.
"""
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1b_lib as L


def jl(p):
    with open(p) as f:
        return json.load(f)


def main():
    runs = []
    for p in sorted(glob.glob(os.path.join(L.RUNS_DIR, "*.json"))):
        if p.endswith("runtime_stamp.json"):
            continue
        r = jl(p)
        if r["tag"].startswith("vid_"):
            continue
        r["_traj"] = os.path.join(L.RUNS_DIR, r["tag"] + "_traj.npz")
        r["_arm"] = r["tag"].split("_")[2] if r["mode"] == "grasp" else "-"
        runs.append(r)

    print("== counts ==")
    n_all = len(runs)
    ng = sum(1 for r in runs if r["mode"] == "grasp")
    ni = sum(1 for r in runs if r["mode"] == "ideal")
    nn = sum(1 for r in runs if r["mode"] == "negctl")
    print("runs(total excl video) %d = grasp %d + ideal %d + negctl %d" % (n_all, ng, ni, nn))

    print("\n== table A: grasp by edge x arm (n / success) ==")
    keys = sorted({(r["edge_mm"], r["_arm"]) for r in runs if r["mode"] == "grasp"})
    hdr = "%-9s" % "arm"
    edges = sorted({r["edge_mm"] for r in runs})
    for e in edges:
        hdr += " | e%dm" % e
    print(hdr)
    for a in sorted({k[1] for k in keys}):
        line = "%-9s" % a
        for e in edges:
            sel = [r for r in runs if r["mode"] == "grasp" and r["edge_mm"] == e and r["_arm"] == a]
            line += " | %2d/%2d" % (sum(1 for r in sel if r["success"]), len(sel)) if sel else " |   --  "
        print(line)

    print("\n== table B: grasp detail (mean over runs) ==")
    for e in edges:
        for a in sorted({k[1] for k in keys if k[0] == e}):
            sel = [r for r in runs if r["mode"] == "grasp" and r["edge_mm"] == e and r["_arm"] == a]
            lf = np.mean([r["lift_final_m"] for r in sel])
            lm = np.mean([r["lift_max_m"] for r in sel])
            rs = np.mean([r["release_slip_m"] or 0 for r in sel])
            rd = np.mean([r["release_drop_m"] or 0 for r in sel])
            cf = np.mean([r["contact_frac_lift"] for r in sel])
            fm = np.mean([r["fi_max_N"] for r in sel])
            close_fi, post_steps = [], []
            for r in sel:
                z = np.load(r["_traj"])
                close_fi.append(float(z["fi"][250:650].max()))
                post_steps.append(int((z["fi"][650:] > 0.02).sum()))
            print("e%02d %-4s n=%2d lift_final_avg=%+.4f lift_max_avg=%.4f realslip_avg=%.4f "
                  "reldrop_avg=%.4f frac_avg=%.2f fi_avg=%.2f | close_fi_max_avg=%.2f "
                  "post_release_contact_steps_avg=%.0f(max %d)"
                  % (e, a, len(sel), lf, lm, rs, rd, cf, fm,
                     float(np.mean(close_fi)), float(np.mean(post_steps)), int(np.max(post_steps))))

    print("\n== table C: controls ==")
    for e in edges:
        for m in ("ideal", "negctl"):
            sel = [r for r in runs if r["mode"] == m and r["edge_mm"] == e]
            if not sel:
                continue
            print("%s e%02d: %d/%d success | lift_final_avg=%.4f frac_avg=%.2f"
                  % (m, e, sum(1 for r in sel if r["success"]), len(sel),
                     np.mean([r["lift_final_m"] for r in sel]),
                     np.mean([r["contact_frac_lift"] for r in sel])))

    print("\n== closest-to-gate runs (smallest release_slip) ==")
    g = [r for r in runs if r["mode"] == "grasp"]
    g.sort(key=lambda r: (r["release_slip_m"] if r["release_slip_m"] is not None else 9))
    for r in g[:6]:
        print("  %-20s realslip=%.5f reldrop=%.5f lift_max=%.4f frac=%.2f fail=%s"
              % (r["tag"], r["release_slip_m"], r["release_drop_m"], r["lift_max_m"],
                 r["contact_frac_lift"], r["fail_reason"]))
    print("\n== failure reasons histogram (grasp) ==")
    hist = {}
    for r in g:
        key = (r["fail_reason"] or "none").split("(")[0]
        hist[key] = hist.get(key, 0) + 1
    for k, v in sorted(hist.items(), key=lambda kv: -kv[1]):
        print("  %-20s %d" % (k, v))
    # runs where the slip gate passed but lift did not
    ok_slip = [r for r in g if (r["release_slip_m"] is not None and r["release_slip_m"] < 0.005)]
    print("  (release_slip < 5 mm: %d runs; of these lift_max>=0.10 m: %d)"
          % (len(ok_slip), sum(1 for r in ok_slip if r["lift_max_m"] >= 0.10)))

    # placement + variant record essentials
    rec = jl(os.path.join(L.PROBE_DIR, "pads_variant_record.json"))
    print("\n== variant record ==")
    print("official model sha256: %s" % rec["official_model_sha256"])
    print("variant xml sha256   : %s" % rec["variant_sha256"])
    print("ghosted right-hand collision geoms (%d): %s" % (
        len(rec["ghosted_collision_geoms_right_hand"]),
        "; ".join(g_.strip()[:64] for g_ in rec["ghosted_collision_geoms_right_hand"])))
    for k, v in rec["pads"].items():
        print("pad %-6s %s r=%.4f center_body=%s protrude=%.4f condim=%d friction=%s"
              % (k, v["geom_name"], v["r"], v["center_body"], v["protrusion_beyond_tip_m"],
                 v["condim"], v["friction"]))
    print("kept collision inventory: thumb %s index %s middle %s palm %s"
          % (rec["kept_collision_inventory"]["thumb"], rec["kept_collision_inventory"]["index"],
             rec["kept_collision_inventory"]["middle"], rec["kept_collision_inventory"]["palm"]))
    for pair in ("ti", "tm"):
        pl = jl(os.path.join(L.PROBE_DIR, "placement_pads_%s.json" % pair))
        print("\nplacement arm %s:" % pair)
        for sz, v in sorted(pl["sizes"].items(), key=lambda kv: int(kv[0])):
            c = v["chosen"]
            print("  e%02d %s lam0=%.4f lam_g=%.4f P=%s da_g=%+.4f db_g=%+.4f dthird=%+.4f squeeze=%.4f"
                  % (int(sz), c["pair"], c["lam"], c["lam_g"], c["P"], c["da_g"], c["db_g"],
                     c["dthird_g"], c["squeeze_g"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
