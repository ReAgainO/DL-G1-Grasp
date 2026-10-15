"""ws1 placement picker v3.

For each cube size:
  - from the measured no-cube closure curve, find lambda_ideal per tip-pair
    (ti = thumb-index, tm = thumb-middle) where pair surface gap = s+4 mm
    (evaluate lambda in [lam_ideal-0.05, lam_ideal+0.05]);
  - place cube at the pair-centre and balance 3x along the pair axis with the
    real cube geom;
  - audits (all static, FK only):
      clr0    : min cube<->hand clearance at lambda=0 (open, spawn) >= +0.5 mm
      pinch_g : the two pinch groups at lambda_g = lam+0.10, both must be
                <= -1 mm (real squeeze)
      third   : the third finger of (thumb/index/middle) at lambda_g >= 0
      palm    : palm at lambda_g >= +2 mm
      post    : min hand<->pedestal-post clearance at lambda_g >= +1.5 mm
                (post = 40x40 mm square, top at cube bottom - 0.5 mm)
  - pick: valid candidates only; rank by pinched total (capped 14 mm), then lam.
Writes placement.json + per-size scene XML via ws1_make_scene.write_scene.
"""
import json
import os
import sys

import numpy as np

import mujoco

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1_lib as L
import ws1_make_scene as S

DUMMY_XML = os.path.join(L.MODEL_DIR, "ws1_scene_dummy.xml")
POST_HALF = 0.02
LAM_EXTRA = 0.10


def main():
    S.make_scene_model()
    S.write_scene(20, (0.8, 0.0, 0.6), (0.8, 0.0), (POST_HALF, POST_HALF), 0.58,
                  (1.0, -0.6, 1.7), (-0.5, 0.45, -0.9), DUMMY_XML)
    specs = L.jload(os.path.join(L.PROBE_DIR, "grasp_specs.json"))
    curve = L.jload(os.path.join(L.PROBE_DIR, "closure_curve.json"))["curve"]
    armv = specs["arm_vals"]
    O7 = np.array(specs["O7"])
    T7 = np.array(specs["T7"])

    m = mujoco.MjModel.from_xml_path(DUMMY_XML)
    d = mujoco.MjData(m)
    cubj = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "cube_free")
    ca = m.jnt_qposadr[cubj]
    cube_g = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "cube_geom")
    ped_g = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "pedestal_top")
    armjid = {n: m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)]
              for n in L.RIGHT_ARM_JOINTS}
    ha = {n: m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)]
          for n in L.RH_JOINTS}
    for n, v in zip(L.RIGHT_ARM_JOINTS, armv):
        d.qpos[armjid[n]] = v
    groups = L.finger_groups(m)
    tips = {
        "th": L.body_geom_ids(m, "right_hand_thumb_2_link"),
        "ix": L.body_geom_ids(m, "right_hand_index_1_link"),
        "md": L.body_geom_ids(m, "right_hand_middle_1_link"),
    }
    allh = groups["thumb"] + groups["index"] + groups["middle"] + groups["palm"]
    ft = np.zeros(6)

    def fk(lam):
        for n, v in zip(L.RH_JOINTS, O7 + lam * (T7 - O7)):
            d.qpos[ha[n]] = v

    def kin():
        mujoco.mj_kinematics(m, d)
        mujoco.mj_comPos(m, d)

    def gd(g1, g2, cap=0.5):
        return float(mujoco.mj_geomDistance(m, d, g1, g2, cap, ft))

    def min_to(glist):
        return min(gd(cube_g, g) for g in glist)

    def set_cube(P):
        d.qpos[ca:ca + 3] = P
        d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]

    def lam_of_gap(pair, target):
        # bisect on the measured no-cube curve
        key = {"ti": "ti", "tm": "tm"}[pair]
        prev = None
        for e in curve:
            w = e["pairs"][key]
            if prev is not None and prev[1] >= target >= w:
                f = (prev[1] - target) / (prev[1] - w)
                return prev[0] + f * (e["lam"] - prev[0])
            if prev is not None and prev[1] <= target <= w:
                f = (target - prev[1]) / (w - prev[1])
                return prev[0] + f * (e["lam"] - prev[0])
            prev = (e["lam"], w)
        return None

    def evaluate(edge, pair, lam):
        s = edge / 1000.0
        s2 = s / 2.0
        m.geom_size[cube_g] = [s2, s2, s2]
        m.geom_rbound[cube_g] = float(s2 * 1.7320508)
        ka, kb = {"ti": ("th", "ix"), "tm": ("th", "md")}[pair]
        ga = {"th": "thumb", "ix": "index", "md": "middle"}[ka]
        gb = {"th": "thumb", "ix": "index", "md": "middle"}[kb]
        third = ({"thumb", "index", "middle"} - {ga, gb}).pop()
        fk(lam)
        kin()
        pa = d.geom_xpos[tips[ka][0]].copy()
        pb = d.geom_xpos[tips[kb][0]].copy()
        axis = pb - pa
        axis /= np.linalg.norm(axis)
        P = 0.5 * (pa + pb)
        for _ in range(4):
            set_cube(P)
            kin()
            da = min_to(tips[ka])
            db = min_to(tips[kb])
            P = P + axis * (db - da) / 2.0
        set_cube(P)
        fk(lam)
        kin()
        da = min_to(tips[ka])
        db = min_to(tips[kb])
        lam_g = min(0.98, lam + LAM_EXTRA)
        # spawn audit
        fk(0.0)
        kin()
        clr0 = min_to(allh)
        # closed audits
        fk(lam_g)
        kin()
        dga = min_to(groups[ga])
        dgb = min_to(groups[gb])
        dthird = min_to(groups[third])
        dpalm = min_to(groups["palm"])
        # post audit: move pedestal under P with proper top
        top = P[2] - s2 - 0.0005
        m.geom_pos[ped_g] = [P[0], P[1], top / 2.0]
        m.geom_size[ped_g] = [POST_HALF, POST_HALF, top / 2.0]
        m.geom_rbound[ped_g] = float(np.sqrt(3) * max(POST_HALF, top / 2.0))
        kin()
        dpost = min(gd(ped_g, g) for g in allh)
        return {
            "pair": pair, "lam": round(float(lam), 4), "lam_g": round(float(lam_g), 4),
            "P": [round(float(v), 6) for v in P],
            "clr0": round(clr0, 5), "pinch_a": round(dga, 5), "pinch_b": round(dgb, 5),
            "third": round(dthird, 5), "palm": round(dpalm, 5), "post": round(dpost, 5),
            "da_at_lam": round(da, 5), "db_at_lam": round(db, 5),
        }

    out = {"arm_vals": armv, "O7": list(map(float, O7)), "T7": list(map(float, T7)),
           "lam_extra": LAM_EXTRA, "post_half": POST_HALF, "sizes": {}}
    for edge in (20, 25, 35):
        s = edge / 1000.0
        rows = []
        for pair in ("ti", "tm"):
            li = lam_of_gap(pair, s + 0.004)
            if li is None:
                continue
            for lam in np.arange(max(0.02, li - 0.05), min(0.94, li + 0.0501), 0.0125):
                rows.append(evaluate(edge, pair, float(lam)))
        valid = [r for r in rows if r["clr0"] >= 0.0005 and r["pinch_a"] <= -0.001
                 and r["pinch_b"] <= -0.001 and r["third"] >= 0.0 and r["palm"] >= 0.002
                 and r["post"] >= 0.0015]
        valid.sort(key=lambda r: (-min(0.014, -(r["pinch_a"] + r["pinch_b"])), -r["lam"]))
        out["sizes"][str(edge)] = {"rows": rows, "valid": valid}
        print("=== size", edge, "n_rows=%d n_valid=%d" % (len(rows), len(valid)))
        for r in rows:
            print("   %s lam=%.3f lam_g=%.3f clr0=%+.4f pinch=%+.4f/%+.4f third=%+.4f palm=%+.4f post=%+.4f P=%s" % (
                r["pair"], r["lam"], r["lam_g"], r["clr0"], r["pinch_a"], r["pinch_b"],
                r["third"], r["palm"], r["post"], r["P"]))
        if valid:
            best = valid[0]
            out["sizes"][str(edge)]["chosen"] = best
            P = np.array(best["P"])
            ped_top = P[2] - s / 2.0 - 0.0005
            p = S.write_scene(edge, P, (P[0], P[1]), (POST_HALF, POST_HALF), ped_top,
                              (P[0] + 0.6, P[1] - 0.6, 1.7), (-0.5, 0.45, -0.9),
                              os.path.join(L.MODEL_DIR, "ws1_scene_%dmm.xml" % edge))
            out["sizes"][str(edge)]["scene"] = p
            out["sizes"][str(edge)]["ped_top"] = round(float(ped_top), 6)
            print("   CHOSEN %s lam=%.3f P=%s" % (best["pair"], best["lam"], best["P"]))
        else:
            print("   NO VALID CANDIDATE for size", edge)
    L.jdump(out, os.path.join(L.PROBE_DIR, "placement.json"))
    L.jdump(L.stamp({"dt": m.opt.timestep}), os.path.join(L.PROBE_DIR, "runtime_stamp_place.json"))
    print("placement.json written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
