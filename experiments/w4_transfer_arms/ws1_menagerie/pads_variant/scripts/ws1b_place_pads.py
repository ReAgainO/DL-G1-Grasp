"""ws1b pads placement picker v2: cube spot calibrated for the PADS-ONLY collision model.

Why (measured, ws1b_calib_pads.py): W1's placement.json was calibrated against the
original whole-hand hull model; at W1's cube spot the three pad spheres never reach
the cube (closest approach > 0.5 mm over the whole closure sweep at e20) -- the
hull pinch was happening via the distal-link SIDES, not the tips. The variant
therefore needs its own seating. Same idea as ws1_place.py v3, re-pointed at the
pads; all run/judging criteria unchanged.

v2 procedure per size and pair (ti = thumb-index, tm = thumb-middle):
  1. grid sweep lambda: cube centre = pad-centre midpoint, balanced 4x along the
     pad axis (min distances to the two pads equalised, W1's balance loop);
     record d_pair(lambda) (= da = db after balance) and dc(lambda).
  2. lambda0 = zero crossing of d_pair (cube exactly fits between the two pad
     spheres); P0 by linear interpolation of the balanced P.
  3. full runner-rule evaluation at P0: lambda_touch = first lambda with min
     pad-cube distance <= 0.5 mm (runner's sweep), lambda_g = min(0.985,
     lambda_touch + lam_extra); squeeze depths of both pads at lambda_g, third
     pad, cube-between-pads test, clr0 at lambda=0, desk clearance.
  accept if: clr0 >= +0.5 mm, desk ok, both pads squeeze (<= -0.25 mm), total
  squeeze <= 5 mm, third pad >= -0.2 mm, cube centre between the pad centres
  (0.25..0.75 of dc, off-axis <= 8 mm).
  rank: squeeze towards 3 mm, then closer third pad, then larger lambda_g.

Writes out/probe/placement_pads.json (W1 layout + rows/candidates/chosen).
"""
import argparse
import os
import sys

import numpy as np

import mujoco

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1b_lib as L

DESK_TOP = 0.80
LAM_EXTRA = 0.06


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", default="20,25,35")
    ap.add_argument("--r", type=float, default=0.005)
    ap.add_argument("--inset-frac", type=float, default=0.7)
    ap.add_argument("--lam-grid", type=float, default=0.01)
    ap.add_argument("--squeeze-cap", type=float, default=0.005)
    args = ap.parse_args()
    edges = [int(v) for v in args.edges.split(",")]

    rec = L.jload(os.path.join(L.PROBE_DIR, "pads_variant_record.json"))
    pl0 = L.jload(os.path.join(L.PROBE_DIR, "placement.json"))
    armv, O7, T7 = pl0["arm_vals"], np.array(pl0["O7"]), np.array(pl0["T7"])

    m = mujoco.MjModel.from_xml_path(os.path.join(L.MODEL_DIR, "ws1b_scene_20mm.xml"))
    d = mujoco.MjData(m)
    pads = L.pad_ids(m)
    for k, g in pads.items():
        tip = np.array(rec["pads"][k]["tip_body"])
        dirv = np.array(rec["pads"][k]["dir_body"])
        m.geom_size[g] = [args.r, 0, 0]
        m.geom_rbound[g] = args.r
        m.geom_pos[g] = tip - args.inset_frac * args.r * dirv
    cube_g = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "cube_geom")
    cubj = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "cube_free")
    ca = m.jnt_qposadr[cubj]
    ha = {n: m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)] for n in L.RH_JOINTS}
    armjid = {n: m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)]
              for n in L.RIGHT_ARM_JOINTS}
    arm_aid = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in L.RIGHT_ARM_JOINTS}
    fing_aid = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n) for n in L.RH_JOINTS}
    ft = np.zeros(6)

    def kin():
        mujoco.mj_kinematics(m, d)
        mujoco.mj_comPos(m, d)

    # ---- settle the arm pose under gravity (same probe as ws1b_run.py) ------
    # The 5 mm pads need the true in-sim hand pose: the arm sags ~10 mm from the
    # commanded FK pose, which moves lambda_touch by ~0.07 and made pads miss the
    # cube entirely when seating was computed from the commanded pose. Fingers are
    # OPEN during the settle so the pads never touch the welded cube.
    SETTLE_STEPS, SETTLE_LAM = 650, 0.0
    mujoco.mj_resetDataKeyframe(m, d, 0)
    for n, v in zip(L.RIGHT_ARM_JOINTS, armv):
        d.qpos[armjid[n]] = v
        d.ctrl[arm_aid[n]] = v
    for i, n in enumerate(L.RH_JOINTS):
        d.qpos[ha[n]] = O7[i] + SETTLE_LAM * (T7[i] - O7[i])
        d.ctrl[fing_aid[n]] = d.qpos[ha[n]]
    d.qpos[ca:ca + 3] = pl0["sizes"]["20"]["chosen"]["P"] if "20" in pl0["sizes"] else [0.4, -0.05, 0.88]
    d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]
    mujoco.mj_forward(m, d)
    for _ in range(SETTLE_STEPS):
        mujoco.mj_step(m, d)
    base_qpos = d.qpos.copy()
    arm_sag = {n: round(float(base_qpos[armjid[n]] - v), 5)
               for n, v in zip(L.RIGHT_ARM_JOINTS, armv)}
    print("settled pose: base z=%.4f | arm deltas %s" % (base_qpos[2], arm_sag))

    def fk(lam):
        cq = d.qpos[ca:ca + 7].copy()
        d.qpos[:] = base_qpos
        d.qpos[ca:ca + 7] = cq
        for i, n in enumerate(L.RH_JOINTS):
            d.qpos[ha[n]] = O7[i] + lam * (T7[i] - O7[i])
        kin()

    def gd(g1, g2, cap=0.4):
        return float(mujoco.mj_geomDistance(m, d, g1, g2, cap, ft))

    def set_cube(P):
        d.qpos[ca:ca + 3] = P
        d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]

    def balance(P, axis, ga, gb, iters=4):
        for _ in range(iters):
            set_cube(P)
            kin()
            da = gd(cube_g, ga)
            db = gd(cube_g, gb)
            P = P + axis * (db - da) / 2.0
        return P

    out = {"arm_vals": armv, "O7": list(map(float, O7)), "T7": list(map(float, T7)),
           "lam_extra": LAM_EXTRA, "procedure": "pads_variant_v2 (pad-convergence seating + runner-rule lambda_g)",
           "pad_r": args.r, "pad_inset_frac": args.inset_frac, "sizes": {},
           "settle": {"steps": SETTLE_STEPS, "lam": SETTLE_LAM, "arm_deltas_rad": arm_sag,
                      "base_z": round(float(base_qpos[2]), 5)}}

    for edge in edges:
        s = edge / 1000.0
        s2 = s / 2.0
        m.geom_size[cube_g] = [s2, s2, s2]
        m.geom_rbound[cube_g] = float(s2 * 1.7320508)
        rows, cands = [], []
        for pair, (ka, kb) in (("ti", ("thumb", "index")), ("tm", ("thumb", "middle"))):
            third = ({"thumb", "index", "middle"} - {ka, kb}).pop()
            ga, gb = pads[ka], pads[kb]
            prev = None
            for lam in np.arange(0.01, 0.9601, args.lam_grid):
                fk(lam)
                pa = d.geom_xpos[ga].copy()
                pb = d.geom_xpos[gb].copy()
                dc = float(np.linalg.norm(pb - pa))
                if dc - 2 * args.r < s - 0.010:
                    prev = None
                    continue
                axis = (pb - pa) / dc
                P = balance(0.5 * (pa + pb), axis, ga, gb)
                set_cube(P)
                kin()
                da = gd(cube_g, ga)
                row = {"pair": pair, "lam": round(float(lam), 4), "dc": round(dc, 5),
                       "d_pair": round(da, 5), "P": [round(float(v), 6) for v in P]}
                rows.append(row)
                if prev is not None and (prev["d_pair"] > 0 >= row["d_pair"] or
                                         prev["d_pair"] < 0 <= row["d_pair"]):
                    f = prev["d_pair"] / (prev["d_pair"] - row["d_pair"])
                    lam0 = prev["lam"] + f * (row["lam"] - prev["lam"])
                    P0 = np.array(prev["P"]) + f * (np.array(row["P"]) - np.array(prev["P"]))
                    # ---- full runner-rule evaluation at P0 --------------------
                    set_cube(P0)
                    fk(0.0)
                    kin()
                    clr0 = min(gd(cube_g, g) for g in pads.values())
                    desk_clr0 = float(P0[2] - s2 - DESK_TOP)
                    lam_touch = None
                    for lam in np.arange(0.0, 0.951, 0.01):
                        fk(lam)
                        if min(gd(cube_g, g) for g in pads.values()) <= 0.0005:
                            lam_touch = float(lam)
                            break
                    lam_g = min(0.985, (lam_touch if lam_touch is not None else 0.5) + LAM_EXTRA)
                    fk(lam_g)
                    kin()
                    da_g = gd(cube_g, ga)
                    db_g = gd(cube_g, gb)
                    d3_g = gd(cube_g, pads[third])
                    pa_g = d.geom_xpos[ga].copy()
                    pb_g = d.geom_xpos[gb].copy()
                    dc_g = float(np.linalg.norm(pb_g - pa_g))
                    axis_g = (pb_g - pa_g) / dc_g
                    rel = P0 - pa_g
                    ta = float(rel @ axis_g)
                    perp = float(np.linalg.norm(rel - ta * axis_g))
                    desk_clr_g = float(0.0)  # cube pinned at P0 during close (weld), irrelevant
                    cand = {
                        "pair": pair, "lam": round(float(lam0), 4),
                        "lam0": round(float(lam0), 4), "lam_touch": lam_touch,
                        "lam_g": round(lam_g, 4), "P": [round(float(v), 6) for v in P0],
                        "clr0": round(clr0, 5), "desk_clr0": round(desk_clr0, 5),
                        "da_g": round(da_g, 5), "db_g": round(db_g, 5), "dthird_g": round(d3_g, 5),
                        "squeeze_g": round(-(da_g + db_g), 5),
                        "dc_g": round(dc_g, 5), "between_ta_frac": round(ta / dc_g, 4),
                        "between_perp_m": round(perp, 6),
                    }
                    cand["accept"] = bool(
                        cand["clr0"] >= 0.0005 and cand["desk_clr0"] >= 0.001
                        and cand["da_g"] <= -0.00025 and cand["db_g"] <= -0.00025
                        and cand["squeeze_g"] <= args.squeeze_cap
                        and cand["dthird_g"] >= -0.0002
                        and 0.25 <= cand["between_ta_frac"] <= 0.75
                        and cand["between_perp_m"] <= 0.008)
                    cands.append(cand)
                    print("   CAND %s lam0=%.4f lam_g=%.4f clr0=%+.4f da_g=%+.4f db_g=%+.4f d3=%+.4f "
                          "sqz=%+.4f dc_g=%.4f ta_frac=%.2f perp=%.4f accept=%s P=%s"
                          % (pair, lam0, lam_g, clr0, da_g, db_g, d3_g, cand["squeeze_g"],
                             dc_g, ta / dc_g, perp, cand["accept"], cand["P"]))
                prev = row
        valid = [c for c in cands if c["accept"]]
        valid.sort(key=lambda c: (-min(0.003, c["squeeze_g"]), c["dthird_g"], -c["lam_g"]))
        out["sizes"][str(edge)] = {"rows": rows, "candidates": cands, "valid": valid}
        print("=== size", edge, "n_grid=%d n_cand=%d n_valid=%d" % (len(rows), len(cands), len(valid)))
        if valid:
            best = valid[0]
            out["sizes"][str(edge)]["chosen"] = best
            print("   CHOSEN %s lam0=%.4f lam_g=%.4f P=%s squeeze=%.4f d3=%+.4f" % (
                best["pair"], best["lam0"], best["lam_g"], best["P"], best["squeeze_g"],
                best["dthird_g"]))
        else:
            print("   NO VALID CANDIDATE for size", edge)
    L.jdump(out, os.path.join(L.PROBE_DIR, "placement_pads.json"))

    # ---- per-pair arms: best candidate of each pair per size ----------------
    def rank(c):
        both = bool(c["da_g"] <= -0.00025 and c["db_g"] <= -0.00025)
        return (0 if not both else 1, -abs(c["squeeze_g"] - 0.0025), c["dthird_g"], -c["lam_g"])

    for pair in ("tm", "ti"):
        arm = {"arm_vals": armv, "O7": list(map(float, O7)), "T7": list(map(float, T7)),
               "lam_extra": LAM_EXTRA,
               "procedure": "pads_variant_v2 pair=%s (pad-convergence seating, runner-rule lambda_g)" % pair,
               "pad_r": args.r, "pad_inset_frac": args.inset_frac, "sizes": {}}
        for edge in edges:
            cl = [c for c in out["sizes"][str(edge)]["candidates"] if c["pair"] == pair]
            if not cl:
                print("arm", pair, "size", edge, ": no candidates")
                continue
            best = max(cl, key=rank)
            arm["sizes"][str(edge)] = {"chosen": best,
                                       "candidates": cl,
                                       "n_candidates": len(cl)}
            print("arm %s size %d: lam0=%.4f lam_g=%.4f P=%s da_g=%+.4f db_g=%+.4f d3=%+.4f sqz=%+.4f"
                  % (pair, edge, best["lam0"], best["lam_g"], best["P"], best["da_g"],
                     best["db_g"], best["dthird_g"], best["squeeze_g"]))
        L.jdump(arm, os.path.join(L.PROBE_DIR, "placement_pads_%s.json" % pair))
    L.jdump(L.stamp({"dt": m.opt.timestep}), os.path.join(L.PROBE_DIR, "runtime_stamp_place_pads.json"))
    print("placement_pads.json + placement_pads_{tm,ti}.json written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
