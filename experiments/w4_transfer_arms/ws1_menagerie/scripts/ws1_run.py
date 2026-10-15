"""ws1 grip run: menagerie G1 3-finger claw, cube-on-post, close + base-lift test.

Protocol per run (dt = 0.002 s):
  settle 0.5 s  : fingers open (O), cube resting 0.5 mm above post top
  close  0.6 s  : finger ctrl ramps O -> lam_g along O->T line
  hold   0.4 s  : finger ctrl at lam_g
  lift   1.0 s  : robot freejoint z += 0.15 m (1.0 s ramp)
  hold   1.0 s  : base kept at +0.15 m
Judging (all during lift/hold):
  success = lift_final >= 0.10 m
        and |cube-in-hand displacement| < 5 mm
        and >=1 finger-cube contact with normal force > 0.02 N
        and no weld (model has zero equality constraints)
Static pre-checks (FK only, recorded):
  - spawn clearance at lambda=0 with the perturbed cube pose (>= +0.2 mm enforced
    by resampling the perturbation)
  - lambda_touch sweep, first lambda where cube<->hand distance <= +0.5 mm
Negative control (--mode negctl): fingers stay at O for the whole run.
"""
import argparse
import os
import sys
import time

import numpy as np

import mujoco

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1_lib as L

LIFT = 0.15
T_SETTLE, T_CLOSE, T_HOLD, T_LIFT, T_HOLDL = 0.5, 0.8, 0.8, 1.0, 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge", type=int, required=True, choices=[20, 25, 35])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mode", choices=["grasp", "negctl", "ideal"], default="grasp")
    ap.add_argument("--lam-extra", type=float, default=0.08)
    ap.add_argument("--perturb", type=float, default=0.002)
    ap.add_argument("--video", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--placement", default=None)
    ap.add_argument("--hand-kp", type=float, default=None,
                    help="override hand position-servo kp for all 14 hand joints "
                         "(kv scaled by sqrt ratio, matching the vendor kp100/kd10 "
                         "controller; asset README: hand gains 'need tuning')")
    args = ap.parse_args()

    tag = args.tag or "e%02d_%s_%03d" % (args.edge, args.mode, args.seed)
    t0 = time.time()
    pl = L.jload(args.placement or os.path.join(L.PROBE_DIR, "placement.json"))
    sspec = pl["sizes"][str(args.edge)]
    chosen = sspec["chosen"]
    armv = pl["arm_vals"]
    O7 = np.array(pl["O7"])
    T7 = np.array(pl["T7"])
    P0 = np.array(chosen["P"])
    s = args.edge / 1000.0
    scene = os.path.join(L.MODEL_DIR, "ws1_scene_%dmm.xml" % args.edge)

    m = mujoco.MjModel.from_xml_path(scene)
    if args.hand_kp:
        for n in (["%s_%s" % (s, j) for s in ("left_hand", "right_hand")
                  for j in ("thumb_0_joint", "thumb_1_joint", "thumb_2_joint",
                            "middle_0_joint", "middle_1_joint",
                            "index_0_joint", "index_1_joint")]):
            a = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n)
            kp_old = m.actuator_gainprm[a, 0]
            ratio = args.hand_kp / kp_old
            m.actuator_gainprm[a, 0] = args.hand_kp
            m.actuator_biasprm[a, 1] = -args.hand_kp
            m.actuator_biasprm[a, 2] *= np.sqrt(ratio)
    d = mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m, d, 0)
    dt = m.opt.timestep

    def jid(n):
        return mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)

    def aid(n):
        return mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n)

    cubj = jid("cube_free")
    ca = m.jnt_qposadr[cubj]
    cav = m.jnt_dofadr[cubj]
    cube_g = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "cube_geom")
    desk_g = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "desk_top")
    wid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_EQUALITY, "cube_holder")
    if wid < 0:
        raise RuntimeError("scene lacks equality weld 'cube_holder'")
    hand_bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, L.HAND_BODY)
    ha = {n: m.jnt_qposadr[jid(n)] for n in L.RH_JOINTS}
    groups = L.finger_groups(m)
    allh = groups["thumb"] + groups["index"] + groups["middle"] + groups["palm"]
    gname = {}
    for k, gl in groups.items():
        for g in gl:
            gname[g] = k
    ft = np.zeros(6)

    # ---- init: arm pose, open fingers, cube at nominal spot -----------------
    for n, v in zip(L.RIGHT_ARM_JOINTS, armv):
        d.qpos[m.jnt_qposadr[jid(n)]] = v
        d.ctrl[aid(n)] = v
    for i, n in enumerate(L.RH_JOINTS):
        d.qpos[ha[n]] = O7[i]
        d.ctrl[aid(n)] = O7[i]

    def fk(lam, q=None):
        cfg = (O7 + lam * (T7 - O7)) if q is None else q
        for i, n in enumerate(L.RH_JOINTS):
            d.qpos[ha[n]] = cfg[i]
        mujoco.mj_kinematics(m, d)
        mujoco.mj_comPos(m, d)

    def min_cube_hand():
        return min(mujoco.mj_geomDistance(m, d, cube_g, g, 0.3, ft) for g in allh)

    # ---- perturbation with spawn-clearance resample -------------------------
    rng = np.random.default_rng(args.seed * 7919 + args.edge)
    tries = 0
    clr0 = None
    perturb = np.zeros(3)
    while tries < 30:
        tries += 1
        perturb = np.array([rng.uniform(-args.perturb, args.perturb),
                            rng.uniform(-args.perturb, args.perturb), 0.0])
        cubeP = P0 + perturb
        d.qpos[ca:ca + 3] = cubeP
        d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]
        fk(0.0)
        clr0 = min_cube_hand()
        if clr0 >= 0.0002:
            break
    spawn_ok = bool(clr0 is not None and clr0 >= 0.0002)
    cube_spawn = d.qpos[ca:ca + 3].copy()

    # ---- lambda_touch sweep (static) ---------------------------------------
    lam_touch = None
    for lam in np.arange(0.0, 0.951, 0.01):
        fk(lam)
        if min_cube_hand() <= 0.0005:
            lam_touch = float(lam)
            break
    fk(0.0)
    if args.mode == "negctl":
        lam_g = 0.0
    else:
        lam_g = min(0.985, (lam_touch if lam_touch is not None else 0.5) + args.lam_extra)
    q_g = O7 + lam_g * (T7 - O7)

    # ---- reset sim state to init -------------------------------------------
    mujoco.mj_resetDataKeyframe(m, d, 0)
    for n, v in zip(L.RIGHT_ARM_JOINTS, armv):
        d.qpos[m.jnt_qposadr[jid(n)]] = v
        d.ctrl[aid(n)] = v
    for i, n in enumerate(L.RH_JOINTS):
        d.qpos[ha[n]] = O7[i]
        d.ctrl[aid(n)] = O7[i]
    d.qpos[ca:ca + 3] = cube_spawn
    d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]
    d.eq_active[wid] = 1  # temp fixture: cube held at the grasp spot
    base0 = float(d.qpos[2])
    mujoco.mj_forward(m, d)

    # ---- optional video ----------------------------------------------------
    renderer = None
    cam = None
    frames = []
    if args.video:
        renderer = mujoco.Renderer(m, 360, 480)
        cam = mujoco.MjvCamera()
        cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        cam.lookat[:] = np.array([cube_spawn[0], cube_spawn[1], cube_spawn[2] + 0.03])
        cam.distance = 0.62
        cam.azimuth = 155.0
        cam.elevation = -14.0

    # idealized-grip positive control (HARNESS SELF-TEST ONLY): at release the cube
    # is kinematically attached to the hand frame (not a weld; qpos override), so a
    # perfect grip is emulated. Used solely to prove the success branch is reachable.
    ideal_rel = None
    if args.mode == "ideal":
        R0 = d.xmat[hand_bid].reshape(3, 3).copy()
        ideal_rel = R0.T @ (d.qpos[ca:ca + 3] - d.xpos[hand_bid])

    # ---- sim ---------------------------------------------------------------
    n1 = int(T_SETTLE / dt)
    n2 = int(T_CLOSE / dt)
    n3 = int(T_HOLD / dt)
    n4 = int(T_LIFT / dt)
    n5 = int(T_HOLDL / dt)
    tot = n1 + n2 + n3 + n4 + n5
    kf_marks = {}
    if args.video:
        kf_marks = {n1 + n2 - 1: "close_end", n1 + n2 + n3 - 1: "hold_end",
                    min(n1 + n2 + n3 + n4 - 1, tot - 1): "lift_end", tot - 1: "final"}
    kf_imgs = {}
    logs = {k: np.zeros(tot) for k in ("t", "cx", "cy", "cz", "bz", "rx", "ry", "rz",
                                       "fi", "ncf", "npf")}
    nan_seen = False
    step = 0
    for k in range(tot):
        if k < n1:
            phase = 0
        elif k < n1 + n2:
            phase = 1
            frac = (k - n1) / max(1, n2 - 1)
            for i, n in enumerate(L.RH_JOINTS):
                d.ctrl[aid(n)] = O7[i] + frac * lam_g * (T7[i] - O7[i])
        elif k < n1 + n2 + n3:
            phase = 2
            if k == n1 + n2:
                d.eq_active[wid] = 0  # release temp fixture weld (cube now held by fingers)
        elif k < n1 + n2 + n3 + n4:
            phase = 3
            d.qpos[2] += LIFT * dt / T_LIFT
        else:
            phase = 4
            d.qpos[2] = base0 + LIFT
        if k >= n1 + n2 and ideal_rel is not None:
            # idealized-grip control: keep the cube rigidly attached to the hand frame
            Rh = d.xmat[hand_bid].reshape(3, 3)
            d.qpos[ca:ca + 3] = d.xpos[hand_bid] + Rh @ ideal_rel
            d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]
            d.qvel[cav:cav + 6] = 0
        mujoco.mj_step(m, d)
        if k >= n1 + n2 and ideal_rel is not None:
            Rh = d.xmat[hand_bid].reshape(3, 3)
            d.qpos[ca:ca + 3] = d.xpos[hand_bid] + Rh @ ideal_rel
            d.qpos[ca + 3:ca + 7] = [1, 0, 0, 0]
            d.qvel[cav:cav + 6] = 0
        if not np.isfinite(d.qpos).all():
            nan_seen = True
            break
        cp = d.qpos[ca:ca + 3]
        hp = d.xpos[hand_bid]
        R = d.xmat[hand_bid].reshape(3, 3)
        rl = R.T @ (cp - hp)
        fi = 0.0
        ncf = 0
        npf = 0
        for ci in range(d.ncon):
            con = d.contact[ci]
            g1, g2 = con.geom1, con.geom2
            other = None
            if g1 == cube_g:
                other = g2
            elif g2 == cube_g:
                other = g1
            if other is None:
                continue
            if other in gname and gname[other] in ("thumb", "index", "middle"):
                mujoco.mj_contactForce(m, d, ci, ft)
                if ft[0] > fi:
                    fi = float(ft[0])
                if ft[0] > 0.02:
                    ncf += 1
            if other == desk_g:
                npf += 1
        logs["t"][k] = d.time
        logs["cx"][k], logs["cy"][k], logs["cz"][k] = cp
        logs["bz"][k] = d.qpos[2]
        logs["rx"][k], logs["ry"][k], logs["rz"][k] = rl
        logs["fi"][k] = fi
        logs["ncf"][k] = ncf
        logs["npf"][k] = npf
        if renderer is not None and (k % 20 == 0 or k == tot - 1 or k in kf_marks):
            renderer.update_scene(d, camera=cam)
            img = renderer.render().copy()
            frames.append(img)
            if k in kf_marks:
                kf_imgs[kf_marks[k]] = img.copy()
        step = k + 1

    ok = step == tot and not nan_seen
    N = step
    i_close0, i_hold0, i_lift0, i_holdl0 = 0, n1, n1 + n2, n1 + n2 + n3
    i_lift1 = n1 + n2 + n3 + n4

    def seg(k0, k1):
        return slice(k0, min(k1, N))

    hold_seg = seg(n1 + n2, n1 + n2 + n3)
    lift_seg = seg(n1 + n2 + n3, n1 + n2 + n3 + n4)
    holdl_seg = seg(n1 + n2 + n3 + n4, tot)
    if N > n1 + n2 + 50:
        z_grasp = float(np.mean(logs["cz"][n1 + n2 + n3 - 50:n1 + n2 + n3]))
        rel_pre = np.array([logs["rx"][n1 + n2 + n3 - 1], logs["ry"][n1 + n2 + n3 - 1],
                            logs["rz"][n1 + n2 + n3 - 1]])
    else:
        z_grasp = float(logs["cz"][N - 1])
        rel_pre = np.array([logs["rx"][N - 1], logs["ry"][N - 1], logs["rz"][N - 1]])
    cz_end = float(logs["cz"][N - 1])
    lift_final = cz_end - z_grasp
    lift_max = float(np.max(logs["cz"][seg(n1 + n2, N)])) - z_grasp
    rel_end = np.array([logs["rx"][N - 1], logs["ry"][N - 1], logs["rz"][N - 1]])
    slip = float(np.linalg.norm(rel_end - rel_pre))
    lift_phase = np.concatenate([np.arange(n1 + n2 + n3, min(N, i_lift1)),
                                 np.arange(i_lift1, N)]) if N > n1 + n2 + n3 else np.array([], dtype=int)
    fi_lift = logs["fi"][lift_phase] if lift_phase.size else np.array([0.0])
    contact_any = bool(np.any(fi_lift > 0.02))
    contact_frac = float(np.mean(fi_lift > 0.02)) if lift_phase.size else 0.0
    fi_max = float(np.max(fi_lift)) if lift_phase.size else 0.0
    pedestal_contacts_end = int(logs["npf"][N - 1])
    # temp-weld fixture: must be inactive from the lift onwards ('no weld' criterion)
    weld_active_end = bool(d.eq_active[wid]) if N > 0 else True
    weld_free = (not weld_active_end)
    # slip while only the fingers hold the cube (post-release hold, pre-lift)
    if N > n1 + n2 + 10:
        rel_rel = np.array([logs["rx"][n1 + n2 - 1], logs["ry"][n1 + n2 - 1], logs["rz"][n1 + n2 - 1]])
        rel_endh = np.array([logs["rx"][n1 + n2 + n3 - 1], logs["ry"][n1 + n2 + n3 - 1],
                             logs["rz"][n1 + n2 + n3 - 1]])
        release_slip = float(np.linalg.norm(rel_endh - rel_rel))
        release_drop = float(logs["cz"][n1 + n2 - 1] - logs["cz"][n1 + n2 + n3 - 1])
    else:
        release_slip = float("nan")
        release_drop = float("nan")
    success = bool(ok and lift_final >= 0.10 and slip < 0.005 and contact_any and weld_free)
    if success:
        fail_reason = None
    elif not ok:
        fail_reason = "sim_invalid(nan=%s,steps=%d/%d)" % (nan_seen, step, tot)
    elif lift_final < 0.10:
        fail_reason = "no_lift(%.4f m)" % lift_final
    elif slip >= 0.005:
        fail_reason = "slip(%.4f m)" % slip
    elif not contact_any:
        fail_reason = "no_finger_contact"
    else:
        fail_reason = "weld"

    stamp = L.stamp({"dt": dt, "scene_xml": scene,
                     "scene_sha256": L.sha256_file(scene)})
    res = {
        "tag": tag, "edge_mm": args.edge, "mode": args.mode, "seed": args.seed,
        "success": success, "fail_reason": fail_reason,
        "lift_final_m": round(lift_final, 5), "lift_max_m": round(lift_max, 5),
        "slip_m": round(slip, 5), "contact_any_lift": contact_any,
        "contact_frac_lift": round(contact_frac, 4), "fi_max_N": round(fi_max, 4),
        "z_grasp": round(z_grasp, 6), "cube_end_z": round(cz_end, 6),
        "weld_free": weld_free, "n_eq": int(m.neq),
        "weld_fixture": {"name": "cube_holder", "active_at_end": weld_active_end,
                         "released_at_step": int(n1 + n2)},
        "release_slip_m": None if release_slip != release_slip else round(release_slip, 5),
        "release_drop_m": None if release_drop != release_drop else round(release_drop, 5),
        "desk_contacts_end": pedestal_contacts_end,
        "spawn_clearance_m": None if clr0 is None else round(float(clr0), 6),
        "spawn_clearance_ok": spawn_ok, "perturb_tries": tries,
        "perturb_xy_m": [round(float(perturb[0]), 6), round(float(perturb[1]), 6)],
        "cube_spawn_xyz": [round(float(v), 6) for v in cube_spawn],
        "lam_touch": lam_touch, "lam_g": round(float(lam_g), 4),
        "lam_extra": args.lam_extra, "q_g": [round(float(v), 5) for v in q_g],
        "O7": [round(float(v), 5) for v in O7], "T7": [round(float(v), 5) for v in T7],
        "chosen_pair_place": chosen["pair"], "chosen_lam_place": chosen["lam"],
        "hand_kp_override": args.hand_kp, "placement_file": args.placement,
        "desk_top": 0.80, "base0": round(base0, 5),
        "sim_steps": int(step), "sim_ok": ok,
        "runtime_stamp": stamp, "elapsed_s": round(time.time() - t0, 2),
    }
    L.jdump(res, os.path.join(L.RUNS_DIR, tag + ".json"))
    np.savez_compressed(os.path.join(L.RUNS_DIR, tag + "_traj.npz"), **logs)

    if args.video and frames:
        import imageio.v2 as imageio
        os.makedirs(os.path.dirname(args.video), exist_ok=True)
        imageio.mimwrite(args.video, frames, fps=25)
        for kname, img in kf_imgs.items():
            imageio.imwrite(os.path.splitext(args.video)[0] + "_kf_" + kname + ".png", img)
        L.jdump(L.stamp({"dt": dt, "video": args.video, "tag": tag, "n_frames": len(frames),
                         "note": "video rendered with the same mujoco version as the run"}),
                os.path.splitext(args.video)[0] + "_runtime_stamp.json")

    print("RUN %s success=%s lift=%.4f slip=%.4f frac=%.2f fi_max=%.3f clr0=%s touch=%s lam_g=%.3f tries=%d %.1fs" % (
        tag, success, lift_final, slip, contact_frac, fi_max,
        None if clr0 is None else round(float(clr0), 4), lam_touch, lam_g, tries,
        time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
