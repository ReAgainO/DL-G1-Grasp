"""Stage-1 static geometry probe (no physics).

Measures, on the official menagerie g1_with_hands.xml right hand (7 joints,
3 fingers):
  [A] hand joint table (names/ranges) -> hand_structure.json
  [B] arm pose grid search: hand curl-axis (wrist_yaw z) vertical & palm in
      reach window -> arm_pose.json (+ grasp_specs.json)
  [C] openness grid search over the 7 finger joints -> open config O
      (max min pairwise tip-tip surface gap)
  [D] thumb_0 scan for the 'tight' config T
  [E] closure curve O->T (lambda 0..1): w(lambda)=min pairwise tip gap,
      midpoint of limiting pair M(lambda)
  [F] per-cube-size feasibility: lambda_s where w = s+4mm (spawn),
      lambda_c where w = s-2mm (interference) -> grasp_specs.json
"""
import itertools
import os
import sys

import numpy as np

import mujoco

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1_lib as L


def kin_only(m, d):
    mujoco.mj_kinematics(m, d)
    mujoco.mj_comPos(m, d)


def geomdist(m, d, g1, g2, distmax=0.2):
    fromto = np.zeros(6)
    return mujoco.mj_geomDistance(m, d, g1, g2, distmax, fromto)


def main():
    os.makedirs(L.PROBE_DIR, exist_ok=True)
    m = mujoco.MjModel.from_xml_path(L.MODEL_XML)
    d = mujoco.MjData(m)
    dt = m.opt.timestep
    model_sha = L.sha256_file(L.MODEL_XML)
    stamp = L.stamp({"dt": dt})
    L.jdump(stamp, os.path.join(L.PROBE_DIR, "runtime_stamp_probe.json"))

    jid = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n) for n in L.RH_JOINTS}
    qadr = {n: m.jnt_qposadr[jid[n]] for n in L.RH_JOINTS}
    jrange = {n: list(np.round(m.jnt_range[jid[n]], 6)) for n in L.RH_JOINTS}
    L.jdump(jrange, os.path.join(L.PROBE_DIR, "hand_joint_table.json"))

    # ---- [B] arm pose grid ------------------------------------------------
    armjid = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n) for n in L.RIGHT_ARM_JOINTS}
    armq = {n: m.jnt_qposadr[armjid[n]] for n in L.RIGHT_ARM_JOINTS}
    hand_bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, L.HAND_BODY)

    grid = itertools.product(
        [-1.4, -1.1, -0.8, -0.5, -0.2],          # shoulder_pitch
        [-0.8, -0.55, -0.3, -0.05, 0.2],         # shoulder_roll
        [-0.8, -0.4, 0.0, 0.4, 0.8],             # shoulder_yaw
        [0.3, 0.6, 0.9, 1.2, 1.5],               # elbow
        [-1.5708, -0.7854, 0.0, 0.7854, 1.5708],  # wrist_roll
        [-0.6, -0.2, 0.2, 0.6],                  # wrist_pitch
        [-0.6, -0.2, 0.2, 0.6],                  # wrist_yaw
    )
    pref = np.array([0.33, -0.18, 0.88])
    cands = []
    for vals in grid:
        d.qpos[:] = 0.0
        d.qpos[2] = 0.79
        d.qpos[3] = 1.0
        for n, v in zip(L.RIGHT_ARM_JOINTS, vals):
            d.qpos[armq[n]] = v
        kin_only(m, d)
        p = d.xpos[hand_bid].copy()
        R = d.xmat[hand_bid].reshape(3, 3)
        zax = R[:, 2]
        xax = R[:, 0]
        if not (0.18 <= p[0] <= 0.55 and -0.42 <= p[1] <= -0.04 and 0.65 <= p[2] <= 1.05):
            continue
        if abs(zax[2]) < 0.90:
            continue
        score = float(abs(zax[2]) - 0.6 * np.linalg.norm(p - pref) - 0.15 * abs(xax[2]))
        cands.append({"vals": [float(v) for v in vals], "palm_xpos": [float(v) for v in p],
                      "zaxis": [float(v) for v in zax], "xaxis": [float(v) for v in xax],
                      "score": score})
    cands.sort(key=lambda c: -c["score"])
    L.jdump({"n_candidates": len(cands), "top": cands[:12]},
            os.path.join(L.PROBE_DIR, "arm_pose.json"))
    if not cands:
        print("PROBE_FAIL: no arm pose satisfies window+z-vertical")
        return 1
    best = cands[0]
    arm_vals = best["vals"]
    print("chosen arm pose:", arm_vals, "palm:", np.round(best["palm_xpos"], 4))

    def set_arm(_d):
        for n, v in zip(L.RIGHT_ARM_JOINTS, arm_vals):
            _d.qpos[armq[n]] = v

    # ---- tip geoms --------------------------------------------------------
    g_th = L.body_geom_ids(m, "right_hand_thumb_2_link")
    g_ix = L.body_geom_ids(m, "right_hand_index_1_link")
    g_md = L.body_geom_ids(m, "right_hand_middle_1_link")

    def w_of(cfg7):
        d.qpos[:] = 0.0
        d.qpos[2] = 0.79
        d.qpos[3] = 1.0
        set_arm(d)
        for n, v in zip(L.RH_JOINTS, cfg7):
            d.qpos[qadr[n]] = v
        kin_only(m, d)
        pairs = {
            "ti": min(geomdist(m, d, a, b) for a in g_th for b in g_ix),
            "tm": min(geomdist(m, d, a, b) for a in g_th for b in g_md),
            "im": min(geomdist(m, d, a, b) for a in g_ix for b in g_md),
        }
        pts = {k: d.geom_xpos[g].copy() for k, g in
               (("th", g_th[0]), ("ix", g_ix[0]), ("md", g_md[0]))}
        return pairs, pts

    # ---- [C] openness grid -------------------------------------------------
    open_sets = [
        [-1.0472, 0.0, 1.0472],           # thumb_0
        [-1.0472, 0.0, 0.724312],         # thumb_1
        [-1.74533, -0.87266, 0.0],        # thumb_2
        [0.0, 0.7854, 1.5708],            # middle_0
        [0.0, 0.87266, 1.74533],          # middle_1
        [0.0, 0.7854, 1.5708],            # index_0
        [0.0, 0.87266, 1.74533],          # index_1
    ]
    best_open, best_w, best_pairs = None, -1e9, None
    n_eval = 0
    for cfg in itertools.product(*open_sets):
        pairs, pts = w_of(np.array(cfg))
        n_eval += 1
        w = min(pairs.values())
        if w > best_w:
            best_w, best_open, best_pairs = w, list(cfg), pairs
    O7 = np.array(best_open)
    L.jdump({"O": best_open, "w_open": best_w, "pairs_at_O": best_pairs, "n_eval": n_eval},
            os.path.join(L.PROBE_DIR, "jaw_open.json"))
    print("open O:", np.round(O7, 3), "w_open=%.4f" % best_w, "pairs=", best_pairs)

    # ---- [D] thumb_0 scan for tight T --------------------------------------
    T_base = {
        "right_hand_thumb_1_joint": -1.0472,
        "right_hand_thumb_2_joint": -1.74533,
        "right_hand_middle_0_joint": 1.5708,
        "right_hand_middle_1_joint": 1.74533,
        "right_hand_index_0_joint": 1.5708,
        "right_hand_index_1_joint": 1.74533,
    }
    scan = []
    for a in np.linspace(-1.0472, 1.0472, 21):
        cfg = [a] + [T_base[n] for n in L.RH_JOINTS[1:]]
        pairs, pts = w_of(np.array(cfg))
        scan.append({"thumb_0": float(a), "pairs": pairs})
    scan.sort(key=lambda e: min(e["pairs"].values()))
    L.jdump({"scan": scan}, os.path.join(L.PROBE_DIR, "thumb0_scan.json"))
    a_star = scan[0]["thumb_0"]
    print("tight T thumb_0=%.3f pairs=%s" % (a_star, scan[0]["pairs"]))

    T7 = np.array([a_star] + [T_base[n] for n in L.RH_JOINTS[1:]])

    # ---- [E] closure curve -------------------------------------------------
    lam = np.linspace(0.0, 1.0, 101)
    curve = []
    for t in lam:
        cfg = O7 + t * (T7 - O7)
        pairs, pts = w_of(cfg)
        kmin = min(pairs, key=pairs.get)
        ptmap = {"ti": ("th", "ix"), "tm": ("th", "md"), "im": ("ix", "md")}[kmin]
        mid = 0.5 * (pts[ptmap[0]] + pts[ptmap[1]])
        curve.append({"lam": float(t), "w": float(pairs[kmin]), "pairs": pairs,
                      "mid": [float(v) for v in mid],
                      "tips": {k: [float(v) for v in p] for k, p in pts.items()}})
    L.jdump({"curve": curve, "O7": list(map(float, O7)), "T7": list(map(float, T7)),
             "arm_vals": arm_vals},
            os.path.join(L.PROBE_DIR, "closure_curve.json"))

    # ---- [F] per-size specs -------------------------------------------------
    sizes_mm = [20.0, 25.0, 35.0]
    specs = {"arm_vals": arm_vals, "O7": list(map(float, O7)), "T7": list(map(float, T7)),
             "w_open": best_w, "hand_body": L.HAND_BODY, "sizes": {}}
    for s_mm in sizes_mm:
        s = s_mm / 1000.0
        spec = {"edge_m": s}
        spawn = None
        interfere = None
        for e in curve:
            if spawn is None and e["w"] <= s + 0.004:
                spawn = e
            if interfere is None and e["w"] <= s - 0.002:
                interfere = e
        spec["w_open_ge_s_plus_4mm"] = bool(best_w >= s + 0.004)
        spec["spawn_lam"] = None if spawn is None else spawn["lam"]
        spec["spawn_mid"] = None if spawn is None else spawn["mid"]
        spec["interfere_lam"] = None if interfere is None else interfere["lam"]
        spec["w_min_over_curve"] = min(e["w"] for e in curve)
        specs["sizes"]["%d" % int(s_mm)] = spec
    L.jdump(specs, os.path.join(L.PROBE_DIR, "grasp_specs.json"))
    L.jdump(stamp, os.path.join(L.PROBE_DIR, "runtime_stamp_probe_after.json"))
    print("PROBE_DONE dt=%s model_sha=%s" % (dt, model_sha[:16]))
    for k, v in specs["sizes"].items():
        print("size", k, "w_open_ok=", v["w_open_ge_s_plus_4mm"], "spawn_lam=", v["spawn_lam"],
              "interfere_lam=", v["interfere_lam"], "w_min=", round(v["w_min_over_curve"], 5))
    return 0


if __name__ == "__main__":
    sys.exit(main())
