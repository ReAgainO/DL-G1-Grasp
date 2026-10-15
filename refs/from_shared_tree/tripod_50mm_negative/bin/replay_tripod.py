#!/usr/bin/env python3
"""Kinematic G1/Dex3 replay with a physically dynamic, contact-only cube.

The source is a previously verified full-body MuJoCo episode. This script
retargets only the right arm and three fingertip joints near ALIGN, then replays
the robot kinematically while MuJoCo integrates the free cube, gravity, table,
and finger contacts. It never activates a weld or writes the source episode.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np


FINGERS = ["right_thumb_fingertip", "right_index_fingertip", "right_middle_fingertip"]
ARM_HAND_JOINTS = [
    "right_shoulder_pitch_joint", "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint", "right_elbow_joint",
    "right_wrist_roll_joint", "right_wrist_pitch_joint",
    "right_wrist_yaw_joint", "right_hand_thumb_0_joint",
    "right_hand_thumb_1_joint", "right_hand_thumb_2_joint",
    "right_hand_index_0_joint", "right_hand_index_1_joint",
    "right_hand_middle_0_joint", "right_hand_middle_1_joint",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def smoothstep(x):
    x = float(np.clip(x, 0.0, 1.0))
    return x * x * (3.0 - 2.0 * x)


def quat_slerp(a, b, u):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    dot = float(np.dot(a, b))
    if dot < 0:
        b, dot = -b, -dot
    dot = min(1.0, max(-1.0, dot))
    if dot > 0.9995:
        q = a + u * (b - a)
        return q / np.linalg.norm(q)
    theta = math.acos(dot)
    return (math.sin((1 - u) * theta) * a + math.sin(u * theta) * b) / math.sin(theta)


def get_body_qpos(m, qpos, obj_qadr, u=0.0):
    """Interpolate only the robot qpos prefix; slerp its floating-base quat."""
    out = qpos.copy()
    if u:
        out[:obj_qadr] = (1.0 - u) * qpos[0][:obj_qadr] + u * qpos[1][:obj_qadr]
        out[3:7] = quat_slerp(qpos[0][3:7], qpos[1][3:7], u)
    return out[:obj_qadr]


def event_times(result):
    return {e["phase"]: float(e["time_s"]) for e in result["events"]}


def phase_at(t, events):
    names = list(events)
    for i, name in enumerate(names):
        if i + 1 == len(names) or t < events[names[i + 1]]:
            return name
    return names[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--trajectory", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--yaw-deg", type=float, default=38.4)
    ap.add_argument("--cube-x", type=float, default=0.48)
    ap.add_argument("--cube-y", type=float, default=0.0)
    ap.add_argument("--approach-ramp-phase", default="PREGRASP",
                    help="begin posture retargeting at this phase")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--video-frames", type=int, default=510,
                    help="uniformly sample the full simulation into this many playback frames")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--playback-speed-label", type=float, default=3.5)
    args = ap.parse_args()

    scene = Path(args.scene)
    traj_path = Path(args.trajectory)
    result_path = Path(args.result)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "keyframes").mkdir(exist_ok=True)

    model = mujoco.MjModel.from_xml_path(str(scene))
    data = mujoco.MjData(model)
    traj = np.load(traj_path, allow_pickle=False)
    source_q = np.asarray(traj["qpos"], dtype=float)
    source_v = np.asarray(traj["qvel"], dtype=float)
    times = np.asarray(traj["time"], dtype=float)
    source_fps = int(np.asarray(traj["fps"]).item())
    result = json.loads(result_path.read_text())
    events = event_times(result)

    cube_joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "red_cube_free")
    cube_geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "red_cube_geom")
    table_geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "table_top")
    cube_qadr = int(model.jnt_qposadr[cube_joint_id])
    cube_dadr = int(model.jnt_dofadr[cube_joint_id])
    finger_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, n) for n in FINGERS]
    protected_body_names = {"right_wrist_pitch_link", "right_wrist_yaw_link",
                            "right_hand_base_link"}
    protected_geom_ids = [g for g in range(model.ngeom)
                          if (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY,
                                                int(model.geom_bodyid[g])) in protected_body_names)]
    joint_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)
                 for n in ARM_HAND_JOINTS]
    joint_qadr = np.array([model.jnt_qposadr[j] for j in joint_ids], dtype=int)
    joint_dadr = np.array([model.jnt_dofadr[j] for j in joint_ids], dtype=int)
    joint_limits = np.array([model.jnt_range[j] for j in joint_ids], dtype=float)

    # Reference scene (same four-legged table/checker floor/ARDY G1/Dex3 style),
    # using the 50 mm object scale visually consistent with the attached clip.
    yaw = math.radians(args.yaw_deg)
    cube_xy = np.array([args.cube_x, args.cube_y])
    table_top_z = 0.757
    half = float(model.geom_size[cube_geom_id, 0])
    cube_center = np.array([cube_xy[0], cube_xy[1], table_top_z + half])
    normal = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    tangent = np.array([-math.sin(yaw), math.cos(yaw), 0.0])

    align_t = events["ALIGN"]
    align_i = int(np.argmin(np.abs(times - align_t)))
    q_align = source_q[align_i].copy()
    q_align[cube_qadr:cube_qadr + 3] = cube_center
    q_align[cube_qadr + 3:cube_qadr + 7] = [math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)]
    x0 = q_align[joint_qadr].copy()

    # Sphere centers at 35 mm from cube center: 25 mm half-size + 10 mm pad
    # radius. Thumb opposes two vertically staggered fingers on one face.
    pad_r = float(model.geom_size[finger_ids[0], 0])
    reach = half + pad_r - 0.001
    targets = np.array([
        cube_center + normal * reach,
        cube_center - normal * reach - tangent * 0.008 + np.array([0, 0, 0.012]),
        cube_center - normal * reach + tangent * 0.008 + np.array([0, 0, -0.012]),
    ])

    def fingertip_centers(x):
        data.qpos[:] = q_align
        data.qpos[joint_qadr] = x
        mujoco.mj_forward(model, data)
        return data.geom_xpos[finger_ids].copy()

    def protected_clearances(x):
        data.qpos[:] = q_align
        data.qpos[joint_qadr] = x
        mujoco.mj_forward(model, data)
        return np.array([mujoco.mj_geomDistance(model, data, int(g), cube_geom_id,
                                                1.0, None) for g in protected_geom_ids])

    x0 = np.clip(x0, joint_limits[:, 0] + 1e-7, joint_limits[:, 1] - 1e-7)

    def ik_residual(x):
        centers = fingertip_centers(x)
        # Keep the targets while allowing the pad spheres to settle on the
        # actual cube surfaces; a weak regularizer prevents gratuitous motion.
        clearances = protected_clearances(x)
        collision = np.maximum(0.0, 0.006 - clearances) / 0.001
        return np.r_[((centers - targets) / 0.01).ravel(), collision * 3.0,
                     (x - x0) * 0.03]

    from scipy.optimize import least_squares
    ik = least_squares(ik_residual, x0, bounds=(joint_limits[:, 0], joint_limits[:, 1]),
                       max_nfev=700, ftol=1e-8, xtol=1e-8, gtol=1e-8)
    x_ik = ik.x.copy()
    actual_centers = fingertip_centers(x_ik)
    pad_distances = [float(mujoco.mj_geomDistance(model, data, int(g), cube_geom_id,
                                                  1.0, None)) for g in finger_ids]
    protected_distances = [float(mujoco.mj_geomDistance(model, data, int(g), cube_geom_id,
                                                         1.0, None)) for g in protected_geom_ids]
    relative = actual_centers - cube_center
    face_side = (relative @ normal).tolist()
    side_gate = face_side[0] > 0 and face_side[1] < 0 and face_side[2] < 0
    static_contact_gate = (all(abs(d) <= 0.002 for d in pad_distances) and side_gate
                           and all(d >= 0.003 for d in protected_distances))
    delta = x_ik - x0

    # Solve a second contact pose 120 mm above the table. We deliberately
    # replace the baseline arm path after alignment: its source lift trajectory
    # is for another cube location and otherwise sweeps the cube sideways.
    def solve_arm_pose(target_centers, seed, max_nfev=700):
        def residual(arm_x):
            x = seed.copy()
            x[:7] = arm_x
            centers = fingertip_centers(x)
            clearances = protected_clearances(x)
            collision = np.maximum(0.0, 0.006 - clearances) / 0.001
            return np.r_[((centers - target_centers) / 0.01).ravel(), collision * 3.0,
                         (arm_x - seed[:7]) * 0.03]
        opt = least_squares(residual, seed[:7],
                            bounds=(joint_limits[:7, 0], joint_limits[:7, 1]),
                            max_nfev=max_nfev, ftol=1e-8, xtol=1e-8, gtol=1e-8)
        full = seed.copy()
        full[:7] = opt.x
        return opt, full

    hover_targets = targets + np.array([0.0, 0.0, 0.075])
    hover_ik, x_hover = solve_arm_pose(hover_targets, x_ik)
    lift_targets = targets + np.array([0.0, 0.0, 0.12])
    lift_ik, x_lift = solve_arm_pose(lift_targets, x_ik, max_nfev=1000)
    descent_poses = [x_hover.copy()]
    descent_heights = np.linspace(0.071, 0.0, 19)
    seed = x_hover.copy()
    for height in descent_heights:
        _, seed = solve_arm_pose(targets + np.array([0.0, 0.0, height]), seed)
        descent_poses.append(seed.copy())
    descent_poses[-1] = x_ik.copy()
    lift_poses = [x_ik.copy()]
    lift_heights = np.linspace(0.006, 0.120, 20)
    seed = x_ik.copy()
    for height in lift_heights:
        _, seed = solve_arm_pose(targets + np.array([0.0, 0.0, height]), seed)
        lift_poses.append(seed.copy())

    # Retarget a single arm path: preposition above the cube -> vertical descent
    # into tripod alignment -> stationary pinch -> vertical lift -> hold. The
    # source episode's post-align hand path belongs to another grasp.
    q_cmd = source_q.copy()
    pre_t = events.get(args.approach_ramp_phase,
                       events.get("PREGRASP", events.get("DESCEND", 0.0)))
    pre_i = int(np.argmin(np.abs(times - pre_t)))
    x_pre = source_q[pre_i, joint_qadr].copy()
    for i, t in enumerate(times):
        if t < events["DESCEND"]:
            # Start the clip in a stable hover pose; the scene reference video
            # begins with the robot already staged behind the table.
            q_cmd[i, joint_qadr] = x_hover
            continue
        if t < align_t:
            u = smoothstep((t - events["DESCEND"]) /
                           max(align_t - events["DESCEND"], 1e-6))
            p = u * (len(descent_poses) - 1)
            j = min(int(p), len(descent_poses) - 2)
            q_cmd[i, joint_qadr] = ((1 - (p - j)) * descent_poses[j]
                                    + (p - j) * descent_poses[j + 1])
        elif t < events["LIFT"]:
            q_cmd[i, joint_qadr] = x_ik
        elif t < events["HOLD"]:
            s = smoothstep((t - events["LIFT"]) /
                           max(events["HOLD"] - events["LIFT"], 1e-6))
            p = s * (len(lift_poses) - 1)
            j = min(int(p), len(lift_poses) - 2)
            q_cmd[i, joint_qadr] = ((1 - (p - j)) * lift_poses[j]
                                    + (p - j) * lift_poses[j + 1])
        else:
            q_cmd[i, joint_qadr] = x_lift
    # The free cube trajectory is not replayed. Only the robot reference prefix
    # is used; cube is initialized once and then integrated dynamically.

    # Disable force actuators in memory: robot motion is prescribed, while the
    # cube, table, gravity and all active collisions remain in the MuJoCo step.
    if model.nu:
        model.actuator_gainprm[:] = 0.0
        model.actuator_biasprm[:] = 0.0
        data.ctrl[:] = 0.0

    data.qpos[:cube_qadr] = q_cmd[0, :cube_qadr]
    data.qpos[cube_qadr:cube_qadr + 3] = cube_center
    data.qpos[cube_qadr + 3:cube_qadr + 7] = [math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)]
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)

    robot_dof_end = cube_dadr
    n = len(times)
    sim_qpos = np.zeros((n, model.nq), dtype=np.float64)
    metrics = []
    table_z = table_top_z
    initial_xy = cube_center[:2].copy()
    timestep = float(model.opt.timestep)

    def command_root_velocity(i, u):
        if source_v.shape[1] >= robot_dof_end:
            data.qvel[:robot_dof_end] = (1-u)*source_v[i, :robot_dof_end] + u*source_v[i+1, :robot_dof_end]

    for i in range(n):
        if i == 0:
            robot_q = q_cmd[i, :cube_qadr]
            data.qpos[:cube_qadr] = robot_q
            data.qvel[:robot_dof_end] = source_v[i, :robot_dof_end]
            mujoco.mj_forward(model, data)
        else:
            dt = float(times[i] - times[i-1])
            steps = max(1, int(round(dt / timestep)))
            dt = steps * timestep
            for k in range(steps):
                u = (k + 1) / steps
                q0 = q_cmd[i-1, :cube_qadr]
                q1 = q_cmd[i, :cube_qadr]
                robot_q = (1-u)*q0 + u*q1
                if cube_qadr >= 7:
                    robot_q[3:7] = quat_slerp(q0[3:7], q1[3:7], u)
                data.qpos[:cube_qadr] = robot_q
                command_root_velocity(i-1, u)
                frame_dt = max(float(times[i] - times[i-1]), timestep)
                for jid, qa, da in zip(joint_ids, joint_qadr, joint_dadr):
                    if model.jnt_type[jid] in (mujoco.mjtJoint.mjJNT_HINGE,
                                               mujoco.mjtJoint.mjJNT_SLIDE):
                        data.qvel[da] = (q1[qa] - q0[qa]) / frame_dt
                data.ctrl[:] = 0.0
                mujoco.mj_forward(model, data)
                mujoco.mj_step(model, data)
            # Pin robot pose exactly at this saved frame; preserve cube state.
            data.qpos[:cube_qadr] = q_cmd[i, :cube_qadr]
            if i < len(source_v):
                data.qvel[:robot_dof_end] = source_v[i, :robot_dof_end]
            mujoco.mj_forward(model, data)

        sim_qpos[i] = data.qpos.copy()
        cube_pos = data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "red_cube")].copy()
        cube_rot = data.geom_xmat[cube_geom_id].reshape(3, 3)
        vertical_half = float(np.sum(np.abs(cube_rot[2, :]) * model.geom_size[cube_geom_id, :3]))
        bottom_clearance = float(cube_pos[2] - vertical_half - table_z)
        contact_fingers = [False, False, False]
        table_contact = False
        for ci in range(data.ncon):
            c = data.contact[ci]
            g1, g2 = int(c.geom1), int(c.geom2)
            if g1 == cube_geom_id or g2 == cube_geom_id:
                other = g2 if g1 == cube_geom_id else g1
                if other == table_geom_id and c.dist <= 0.0005:
                    table_contact = True
                for fi, fg in enumerate(finger_ids):
                    if other == fg and c.dist <= 0.0005:
                        contact_fingers[fi] = True
        slip = float(np.linalg.norm(cube_pos[:2] - initial_xy))
        metrics.append({
            "frame": i, "time_s": float(times[i]), "phase": phase_at(float(times[i]), events),
            "cube_x_m": float(cube_pos[0]), "cube_y_m": float(cube_pos[1]),
            "cube_z_m": float(cube_pos[2]), "cube_bottom_clearance_m": bottom_clearance,
            "cube_slip_from_start_xy_m": slip,
            "thumb_contact": int(contact_fingers[0]), "index_contact": int(contact_fingers[1]),
            "middle_contact": int(contact_fingers[2]), "table_support_contact": int(table_contact),
            "ncon": int(data.ncon),
        })

    hold_start = events["HOLD"]
    hold_end = min(hold_start + 1.0, events.get("RELEASE", hold_start + 1.0))
    hold = [m for m in metrics if hold_start <= m["time_s"] <= hold_end]
    lift_window = [m for m in metrics if events["LIFT"] <= m["time_s"] <= hold_end]
    contact_rate = {f: float(np.mean([row[f + "_contact"] for row in hold])) if hold else 0.0
                    for f in ("thumb", "index", "middle")}
    hold_min_clear = min((row["cube_bottom_clearance_m"] for row in hold), default=-1.0)
    if hold:
        hold_anchor = np.array([hold[0]["cube_x_m"], hold[0]["cube_y_m"]])
        hold_slip = max(float(np.linalg.norm(np.array([row["cube_x_m"], row["cube_y_m"]]) - hold_anchor))
                        for row in hold)
    else:
        hold_slip = float("inf")
    table_support_frames = sum(row["table_support_contact"] for row in hold)
    gates = {
        "three_finger_contact_rate_each_ge_90pct": bool(hold and all(v >= 0.90 for v in contact_rate.values())),
        "hold_bottom_clearance_ge_70mm": bool(hold_min_clear >= 0.07),
        "hold_xy_slip_le_10mm": bool(hold_slip <= 0.01),
        "no_table_support_during_hold": bool(table_support_frames == 0),
        "static_2v1_pose_contact_and_face_sides": bool(static_contact_gate),
    }
    status = "PASS" if all(gates.values()) else "FAIL"

    csv_path = out / "tripod_replay_frames.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)

    summary = {
        "status": status,
        "model": "ARDY/G1 full-body reference + Dex3 three-finger hand; prescribed kinematic robot, dynamic free cube",
        "source_scene": str(scene), "source_scene_sha256": sha256(scene),
        "source_trajectory": str(traj_path), "source_trajectory_sha256": sha256(traj_path),
        "user_reference_video_sha256": sha256(scene.parent.parent / "user_reference_0.mp4")
            if (scene.parent.parent / "user_reference_0.mp4").exists() else None,
        "mujoco_version": mujoco.__version__, "nq": model.nq, "nv": model.nv,
        "nu": model.nu, "neq": model.neq, "timestep_s": timestep,
        "source_fps": source_fps, "frames": n, "sim_duration_s": float(times[-1] - times[0]),
        "cube_edge_m": 2 * half, "cube_mass_kg": float(model.body_mass[
            mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "red_cube")]),
        "cube_initial_center_m": cube_center.tolist(), "table_top_z_m": table_z,
        "table_size_half_m": model.geom_size[table_geom_id].tolist(),
        "cube_yaw_deg": args.yaw_deg, "handpad_radius_m": pad_r,
        "tripod_face_normal_xy": normal[:2].tolist(),
        "tripod_targets_world_m": targets.tolist(),
        "tripod_actual_pad_centers_world_m": actual_centers.tolist(),
        "tripod_pad_distances_to_cube_m": pad_distances,
        "protected_wrist_distances_to_cube_m": protected_distances,
        "tripod_pad_center_signed_face_projection_m": face_side,
        "ik_success_flag": bool(ik.success), "ik_nfev": int(ik.nfev),
        "lift_ik_success_flag": bool(lift_ik.success), "lift_ik_nfev": int(lift_ik.nfev),
        "hover_ik_success_flag": bool(hover_ik.success), "hover_ik_nfev": int(hover_ik.nfev),
        "hover_targets_world_m": hover_targets.tolist(),
        "descent_waypoint_heights_m": [0.075] + descent_heights.tolist(),
        "lift_waypoint_heights_m": [0.0] + lift_heights.tolist(),
        "lift_targets_world_m": lift_targets.tolist(),
        "lift_joint_delta_from_grasp_rad": {name: float(v) for name, v in zip(ARM_HAND_JOINTS, x_lift - x_ik)},
        "ik_joint_delta_rad": {name: float(v) for name, v in zip(ARM_HAND_JOINTS, delta)},
        "hold_window_s": [hold_start, hold_end], "hold_frames": len(hold),
        "hold_contact_rate_each": contact_rate,
        "hold_min_cube_bottom_clearance_m": float(hold_min_clear),
        "hold_max_xy_slip_from_start_m": float(hold_slip),
        "hold_table_support_frames": int(table_support_frames),
        "gates": gates, "physics_scope": "MuJoCo gravity/table/cube/finger contact; no weld; actuators disabled and robot qpos replayed kinematically",
        "not_a_real_robot_test": True,
    }
    summary_path = out / "tripod_replay_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    # Full-body overview, with the entire original task compressed to a clip
    # duration comparable to the supplied ~17 s example. HUD reports source sim time.
    try:
        import cv2
    except ImportError:
        cv2 = None
    render_model = model
    render_data = mujoco.MjData(render_model)
    renderer = mujoco.Renderer(render_model, height=args.height, width=args.width)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(cam)
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = [0.50, -0.06, 0.84]
    cam.distance = 2.50
    cam.azimuth = 140
    cam.elevation = -14
    picks = np.unique(np.linspace(0, n - 1, min(args.video_frames, n)).round().astype(int))
    video_path = out / "ardy_table_tripod_2v1.mp4"
    ffmpeg = os.environ.get("FFMPEG_BINARY", "ffmpeg")
    proc = subprocess.Popen([
        ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{args.width}x{args.height}", "-r", str(args.fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", str(video_path)
    ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for out_i, idx in enumerate(picks):
        render_data.qpos[:] = sim_qpos[idx]
        mujoco.mj_forward(render_model, render_data)
        renderer.update_scene(render_data, camera=cam)
        frame = renderer.render()
        if cv2 is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            cv2.rectangle(frame, (0, 0), (args.width, 55), (17, 31, 47), -1)
            hud1 = f"ARDY / G1 Dex3 | 2:1 SIDE GRIP | {status} | NO WELD"
            hud2 = (f"sim t={times[idx]:.2f}s | {phase_at(float(times[idx]), events)} | "
                    f"cube bottom clearance={metrics[idx]['cube_bottom_clearance_m']*1000:.0f} mm | "
                    f"playback ~{args.playback_speed_label:.1f}x")
            cv2.putText(frame, hud1, (18, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 1, cv2.LINE_AA)
            cv2.putText(frame, hud2, (18, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220,235,247), 1, cv2.LINE_AA)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        if idx in {0, align_i, int(np.argmin(abs(times - events["CLOSE"]))),
                   int(np.argmin(abs(times - events["LIFT"]))),
                   int(np.argmin(abs(times - hold_start))), n - 1}:
            imageio.imwrite(out / "keyframes" / f"frame_{idx:04d}_{phase_at(float(times[idx]), events)}.png", frame)
    proc.stdin.close()
    ffmpeg_err = proc.stderr.read().decode("utf-8", errors="replace")
    ffmpeg_status = proc.wait()
    if ffmpeg_status:
        raise RuntimeError(f"ffmpeg failed ({ffmpeg_status}): {ffmpeg_err[-2000:]}")
    renderer.close()

    summary["video"] = str(video_path)
    summary["video_sha256"] = sha256(video_path)
    summary["video_bytes"] = video_path.stat().st_size
    summary["video_frames"] = len(picks)
    summary["video_fps"] = args.fps
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": status, "gates": gates, "hold_contact_rate_each": contact_rate,
                      "hold_min_cube_bottom_clearance_m": hold_min_clear,
                      "hold_max_xy_slip_from_start_m": hold_slip,
                      "video": str(video_path), "video_sha256": summary["video_sha256"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
