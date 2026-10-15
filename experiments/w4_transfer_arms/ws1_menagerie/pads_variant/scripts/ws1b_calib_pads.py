"""ws1b pads-only static calibration.

For each (r, inset_frac) config and each cube size: replicate W1's spawn
placement (chosen P from placement.json, ±2 mm xy perturbation resample with
>= 0.2 mm clearance), then FK-sweep the finger closure and report:
  clr0        : min cube<->pad distance at lambda=0 (open), pads only
  lam_touch   : first lambda where min cube<->pad distance <= 0.5 mm
  lam_g       : min(0.985, lam_touch + lam_extra)  (matrix uses lam_extra=0.06)
  d_pad(3)    : signed cube<->pad distance at lam_g  (negative = squeeze depth)
  d_hull_min  : min cube<->ghosted-hull distance at lam_g (shows what was
                excluded by the pads-only isolation; also proves that
                mj_geomDistance still measures contype=0 geoms, i.e. the runner
                must filter explicitly)

Writes out/probe/pads_calib.json (all configs, all sizes).
"""
import argparse
import os
import sys

import numpy as np

import mujoco

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1b_lib as L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="0.005:0.7;0.006:0.7;0.005:1.0;0.004:0.7;0.006:1.0",
                    help="semicolon list of r:inset_frac")
    ap.add_argument("--lam-extra", type=float, default=0.06)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    configs = [tuple(float(v) for v in c.split(":")) for c in args.configs.split(";") if c]

    rec = L.jload(os.path.join(L.PROBE_DIR, "pads_variant_record.json"))
    pl = L.jload(os.path.join(L.PROBE_DIR, "placement.json"))
    armv, O7, T7 = pl["arm_vals"], np.array(pl["O7"]), np.array(pl["T7"])
    out = {"configs": [{"r": c[0], "inset_frac": c[1]} for c in configs], "sizes": {}}
    ft = np.zeros(6)

    for edge_s, sspec in sorted(pl["sizes"].items(), key=lambda kv: int(kv[0])):
        if not sspec.get("chosen"):
            continue
        edge = int(edge_s)
        P0 = np.array(sspec["chosen"]["P"])
        s2 = edge / 1000.0 / 2.0
        scene = os.path.join(L.MODEL_DIR, "ws1b_scene_%dmm.xml" % edge)
        m = mujoco.MjModel.from_xml_path(scene)
        d = mujoco.MjData(m)
        pads = L.pad_ids(m)
        cube_g = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "cube_geom")
        m.geom_size[cube_g] = [s2, s2, s2]
        m.geom_rbound[cube_g] = float(s2 * 1.7320508)
        ha = {n: m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)] for n in L.RH_JOINTS}
        armjid = {n: m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)]
                  for n in L.RIGHT_ARM_JOINTS}
        cubj = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "cube_free")
        ca = m.jnt_qposadr[cubj]
        for n, v in zip(L.RIGHT_ARM_JOINTS, armv):
            d.qpos[armjid[n]] = v
        # ghosted hull geoms (for the exclusion probe): all right-hand geoms that are NOT pads
        ghosts = []
        for b in (L.RH_BODIES_THUMB + L.RH_BODIES_INDEX + L.RH_BODIES_MIDDLE):
            for g in L.body_geom_ids(m, b):
                if g not in pads.values():
                    ghosts.append(g)

        def kin():
            mujoco.mj_kinematics(m, d)
            mujoco.mj_comPos(m, d)

        def fk(lam):
            for n, v in zip(L.RH_JOINTS, O7 + lam * (T7 - O7)):
                d.qpos[ha[n]] = v
            kin()

        def gd(g1, g2, cap=0.3):
            return float(mujoco.mj_geomDistance(m, d, g1, g2, cap, ft))

        def min_pads():
            return min(gd(cube_g, g) for g in pads.values())

        rows = []
        for r, frac in configs:
            for k, g in pads.items():
                tip = np.array(rec["pads"][k]["tip_body"])
                dirv = np.array(rec["pads"][k]["dir_body"])
                m.geom_size[g] = [r, 0, 0]
                m.geom_rbound[g] = r
                m.geom_pos[g] = tip - frac * r * dirv
            # spawn resample (same RNG formula as ws1_run)
            rng = np.random.default_rng(args.seed * 7919 + edge)
            clr_raw = None
            for tries in range(1, 31):
                pert = np.array([rng.uniform(-0.002, 0.002), rng.uniform(-0.002, 0.002), 0.0])
                cubeP = P0 + pert
                d.qpos[ca:ca + 3] = cubeP
                d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]
                fk(0.0)
                clr = min_pads()
                if clr_raw is None:
                    clr_raw = clr
                if clr >= 0.0002:
                    break
            clr0 = clr
            lam_touch = None
            for lam in np.arange(0.0, 0.951, 0.01):
                fk(lam)
                if min_pads() <= 0.0005:
                    lam_touch = float(lam)
                    break
            lam_g = min(0.985, (lam_touch if lam_touch is not None else 0.5) + args.lam_extra)
            fk(lam_g)
            d_pad = {k: round(gd(cube_g, g), 5) for k, g in pads.items()}
            d_hull = round(min(gd(cube_g, g) for g in ghosts), 5) if ghosts else None
            row = {"r": r, "inset_frac": frac, "clr0_raw": round(clr_raw, 5),
                   "clr0_resampled": round(clr0, 5), "tries": tries,
                   "lam_touch": lam_touch, "lam_g": round(lam_g, 4),
                   "d_pad_at_lam_g": d_pad, "d_ghost_hull_min_at_lam_g": d_hull}
            rows.append(row)
            print("e%02d r=%.4f f=%.1f clr0=%+.4f(%d tries, raw %+.4f) touch=%s lam_g=%.3f "
                  "d_pad[th=%+.4f ix=%+.4f md=%+.4f] d_ghosthub=%+.4f"
                  % (edge, r, frac, row["clr0_resampled"], tries, row["clr0_raw"],
                     row["lam_touch"], row["lam_g"], d_pad["thumb"], d_pad["index"],
                     d_pad["middle"], d_hull))
        out["sizes"][edge_s] = {"scene": scene, "P": sspec["chosen"]["P"], "rows": rows}
    L.jdump(out, os.path.join(L.PROBE_DIR, "pads_calib.json"))
    print("pads_calib.json written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
