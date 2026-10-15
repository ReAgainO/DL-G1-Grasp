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
    ap.add_argument("--squeeze-mm", type=float, default=3.0,
                    help="target pad penetration for preload, in mm")
    ap.add_argument("--thumb-squeeze-mm", type=float, default=None)
    ap.add_argument("--index-squeeze-mm", type=float, default=None)
    ap.add_argument("--middle-squeeze-mm", type=float, default=None)
    ap.add_argument("--grip-height-offset-mm", type=float, default=0.0,
                    help="shift all three grasp-pad centers relative to cube center in Z")
    ap.add_argument("--open-gap-mm", type=float, default=2.0,
                    help="radial pad clearance at open/align phase, in mm")
    ap.add_argument("--close-duration-s", type=float, default=2.0)
    ap.add_argument("--confirm-duration-s", type=float, default=0.7)
    ap.add_argument("--lift-duration-s", type=float, default=2.0,
                    help="time from confirmed grasp to the 120 mm lift pose")
    ap.add_argument("--lift-stop-after-s", type=float, default=None,
                    help="optional time to stop the lift and begin HOLD before reaching the full 120 mm pose")
    ap.add_argument("--pad-friction", type=float, default=2.0,
                    help="finger-pad sliding friction coefficient for this simulation")
    ap.add_argument("--pad-adhesion-n", type=float, default=0.0,
                    help="per-contact fingertip adhesion in N (tacky-pad material model; not a weld)")
    ap.add_argument("--cube-friction", type=float, default=2.0,
                    help="cube sliding friction coefficient for finger contact mixing")
    ap.add_argument("--prelift-nudge-mm", type=float, default=0.0,
                    help="brief downward pad motion before the upward lift, to preload side friction")
    ap.add_argument("--prelift-duration-s", type=float, default=0.3)
    ap.add_argument("--track-cube", action="store_true",
                    help="retarget the kinematic arm in XYZ to preserve pad-centroid offset to the free cube")
    ap.add_argument("--track-gain", type=float, default=0.15)
    ap.add_argument("--track-max-dq", type=float, default=0.02)
    ap.add_argument("--lift-extra-close-fraction", type=float, default=0.0,
                    help="extra fraction of open-to-closed joint travel if any pad loses contact during lift")
    ap.add_argument("--lift-extra-thumb-fraction", type=float, default=None)
    ap.add_argument("--lift-extra-index-fraction", type=float, default=None)
    ap.add_argument("--lift-extra-middle-fraction", type=float, default=None)
    ap.add_argument("--contact-preload-fraction", type=float, default=0.25,
                    help="fraction of remaining close travel applied after each fingertip first touches")
    ap.add_argument("--lock-arm-after-first-touch", action="store_true",
                    help="hold arm joints fixed after the first pad touch while other fingers close")
    ap.add_argument("--staged-touch-latch", action="store_true",
                    help="use per-finger touch/preload/retry during the close phase")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--video-frames", type=int, default=510,
                    help="uniformly sample the full simulation into this many playback frames")
    ap.add_argument("--control-mode", choices=("kinematic", "torque_pd"), default="kinematic",
                    help="direct kinematic replay or dynamic joint-motor PD tracking")
    ap.add_argument("--arm-kp", type=float, default=60.0)
    ap.add_argument("--arm-kd", type=float, default=8.0)
    ap.add_argument("--hand-kp", type=float, default=8.0)
    ap.add_argument("--hand-kd", type=float, default=1.5)
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
    model.geom_friction[finger_ids, 0] = args.pad_friction
    model.geom_adhesion[finger_ids] = args.pad_adhesion_n
    model.geom_friction[cube_geom_id, 0] = args.cube_friction
    data = mujoco.MjData(model)
    ik_data = mujoco.MjData(model)
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

    # Sphere centers near the cube mid-height: thumb on one face opposes two
    # pads on the other face, spread along the edge rather than vertically.
    pad_r = float(model.geom_size[finger_ids[0], 0])
    finger_squeeze = [
        args.squeeze_mm if args.thumb_squeeze_mm is None else args.thumb_squeeze_mm,
        args.squeeze_mm if args.index_squeeze_mm is None else args.index_squeeze_mm,
        args.squeeze_mm if args.middle_squeeze_mm is None else args.middle_squeeze_mm,
    ]
    reaches = half + pad_r - np.asarray(finger_squeeze, dtype=float) / 1000.0
    targets = np.array([
        cube_center + normal * reaches[0],
        cube_center - normal * reaches[1] - tangent * 0.010,
        cube_center - normal * reaches[2] + tangent * 0.010,
    ])
    targets[:, 2] += args.grip_height_offset_mm / 1000.0

    def fingertip_centers(x):
        ik_data.qpos[:] = q_align
        ik_data.qpos[joint_qadr] = x
        mujoco.mj_forward(model, ik_data)
        return ik_data.geom_xpos[finger_ids].copy()

    def protected_clearances(x):
        ik_data.qpos[:] = q_align
        ik_data.qpos[joint_qadr] = x
        mujoco.mj_forward(model, ik_data)
        return np.array([mujoco.mj_geomDistance(model, ik_data, int(g), cube_geom_id,
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
                       max_nfev=1500, ftol=1e-8, xtol=1e-8, gtol=1e-8)
    x_ik = ik.x.copy()
    actual_centers = fingertip_centers(x_ik)
    pad_distances = [float(mujoco.mj_geomDistance(model, ik_data, int(g), cube_geom_id,
                                                  1.0, None)) for g in finger_ids]
    protected_distances = [float(mujoco.mj_geomDistance(model, ik_data, int(g), cube_geom_id,
                                                         1.0, None)) for g in protected_geom_ids]
    relative = actual_centers - cube_center
    face_side = (relative @ normal).tolist()
    side_gate = face_side[0] > 0 and face_side[1] < 0 and face_side[2] < 0
    static_contact_gate = (all(abs(d) <= 0.010 for d in pad_distances) and side_gate
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

    def solve_hand_pose(target_centers, seed, max_nfev=700):
        """Change only finger joints so opening/closing cannot sweep the wrist."""
        def residual(hand_x):
            x = seed.copy()
            x[7:] = hand_x
            centers = fingertip_centers(x)
            clearances = protected_clearances(x)
            collision = np.maximum(0.0, 0.006 - clearances) / 0.001
            return np.r_[((centers - target_centers) / 0.01).ravel(), collision * 3.0,
                         (hand_x - seed[7:]) * 0.03]
        opt = least_squares(residual, seed[7:],
                            bounds=(joint_limits[7:, 0], joint_limits[7:, 1]),
                            max_nfev=max_nfev, ftol=1e-8, xtol=1e-8, gtol=1e-8)
        full = seed.copy()
        full[7:] = opt.x
        return opt, full

    def solve_full_pose(target_centers, seed, max_nfev=1200):
        """Solve arm and hand together for an approach pose near a known grip."""
        def residual(x):
            centers = fingertip_centers(x)
            clearances = protected_clearances(x)
            collision = np.maximum(0.0, 0.006 - clearances) / 0.001
            return np.r_[((centers - target_centers) / 0.01).ravel(), collision * 3.0,
                         (x - seed) * 0.03]
        opt = least_squares(residual, seed,
                            bounds=(joint_limits[:, 0], joint_limits[:, 1]),
                            max_nfev=max_nfev, ftol=1e-8, xtol=1e-8, gtol=1e-8)
        return opt, opt.x.copy()

    # Build the open pose by offsetting the *reachable* closed-pose pad centers,
    # then allow arm and fingers to solve together (hand-only opening was not
    # reachable for this coplanar three-pad layout).
    open_gap = args.open_gap_mm / 1000.0
    open_offsets = np.array([normal * open_gap, -normal * open_gap, -normal * open_gap])
    open_targets = actual_centers + open_offsets
    open_seed = x_ik.copy()
    open_ik, x_open = solve_full_pose(open_targets, open_seed)
    open_actual_centers = fingertip_centers(x_open)
    open_pad_target_errors = np.linalg.norm(open_actual_centers - open_targets, axis=1)
    close_poses = [x_open.copy()]
    close_pose_errors = [float(np.max(np.linalg.norm(open_actual_centers - open_targets, axis=1)))]
    close_seed = x_open.copy()
    for u in np.linspace(0.05, 1.0, 20):
        close_targets = actual_centers + open_offsets * (1.0 - u)
        if u >= 1.0:
            close_seed = x_ik.copy()
        else:
            _, close_seed = solve_full_pose(close_targets, close_seed)
        close_poses.append(close_seed.copy())
        close_pose_errors.append(float(np.max(np.linalg.norm(
            fingertip_centers(close_seed) - close_targets, axis=1))))
    hover_targets = open_targets + np.array([0.0, 0.0, 0.075])
    hover_ik, x_hover = solve_arm_pose(hover_targets, x_open)
    # Lift from the reachable FK centers, not the nominal IK targets; the
    # same-side pads can settle tangentially on the face several mm away.
    lift_targets = actual_centers + np.array([0.0, 0.0, 0.12])
    lift_ik, x_lift = solve_arm_pose(lift_targets, x_ik, max_nfev=1000)
    lift_actual_centers = fingertip_centers(x_lift)
    lift_pad_target_errors = np.linalg.norm(lift_actual_centers - lift_targets, axis=1)
    if abs(args.prelift_nudge_mm) < 1e-9:
        # Avoid an unnecessary second IK solve: even identical Cartesian
        # targets can select a different arm branch and create an unintended
        # motion during what should be a zero-length preload transition.
        nudge_ik = None
        x_nudge = x_ik.copy()
    else:
        nudge_targets = actual_centers + np.array(
            [0.0, 0.0, -args.prelift_nudge_mm / 1000.0])
        nudge_ik, x_nudge = solve_arm_pose(nudge_targets, x_ik, max_nfev=1000)
    descent_poses = [x_hover.copy()]
    descent_heights = np.linspace(0.071, 0.0, 19)
    seed = x_hover.copy()
    for height in descent_heights:
        _, seed = solve_arm_pose(open_targets + np.array([0.0, 0.0, height]), seed)
        descent_poses.append(seed.copy())
    descent_poses[-1] = x_open.copy()
    lift_poses = [x_nudge.copy()]
    lift_heights = np.linspace(0.006, 0.120, 20)
    seed = x_nudge.copy()
    for height in lift_heights:
        _, seed = solve_arm_pose(actual_centers + np.array([0.0, 0.0, height]), seed)
        lift_poses.append(seed.copy())

    # Explicit phases: open hover -> vertical descent -> close for 1.2 s ->
    # contact confirmation for 0.5 s -> vertical lift -> 2 s hold.
    q_cmd = source_q.copy()
    # Freeze the base, torso and non-participating joints at the aligned
    # standing reference. The source clip's root motion caused geom_89 wrist
    # collisions during hover even though the terminal posture was clear.
    q_cmd[:, :cube_qadr] = source_q[align_i, :cube_qadr]
    descend_start = events["DESCEND"]
    close_start = align_t
    close_end = close_start + args.close_duration_s
    confirm_end = close_end + args.confirm_duration_s
    lift_start = confirm_end + args.prelift_duration_s
    lift_stop_after = (args.lift_duration_s if args.lift_stop_after_s is None
                       else max(0.0, args.lift_stop_after_s))
    hold_start = min(events["HOLD"], lift_start + lift_stop_after)
    hold_progress = smoothstep((hold_start - lift_start) / max(args.lift_duration_s, 1e-6))
    hold_pose_p = hold_progress * (len(lift_poses) - 1)
    hold_pose_j = min(int(hold_pose_p), len(lift_poses) - 2)
    lift_hold_arm_q = ((1 - (hold_pose_p - hold_pose_j)) * lift_poses[hold_pose_j][:7]
                       + (hold_pose_p - hold_pose_j) * lift_poses[hold_pose_j + 1][:7])
    motion_events = {
        "HOVER": 0.0, "DESCEND": descend_start, "ALIGN": align_t,
        "CLOSE": close_start, "CONTACT_CONFIRM": close_end,
        "PRELIFT": confirm_end, "LIFT": lift_start,
        "HOLD": hold_start, "RELEASE": events["RELEASE"],
    }
    for i, t in enumerate(times):
        if t < descend_start:
            # Start the clip in a stable hover pose; the scene reference video
            # begins with the robot already staged behind the table.
            q_cmd[i, joint_qadr] = x_hover
            continue
        if t < align_t:
            u = smoothstep((t - descend_start) / max(align_t - descend_start, 1e-6))
            p = u * (len(descent_poses) - 1)
            j = min(int(p), len(descent_poses) - 2)
            q_cmd[i, joint_qadr] = ((1 - (p - j)) * descent_poses[j]
                                    + (p - j) * descent_poses[j + 1])
        elif t < close_end:
            s = smoothstep((t - close_start) / max(close_end - close_start, 1e-6))
            p = s * (len(close_poses) - 1)
            j = min(int(p), len(close_poses) - 2)
            q_cmd[i, joint_qadr] = ((1 - (p - j)) * close_poses[j]
                                    + (p - j) * close_poses[j + 1])
        elif t < confirm_end:
            q_cmd[i, joint_qadr] = x_ik
        elif t < lift_start:
            s = smoothstep((t - confirm_end) / max(args.prelift_duration_s, 1e-6))
            q_cmd[i, joint_qadr] = (1 - s) * x_ik + s * x_nudge
        elif t < hold_start:
            s = smoothstep((t - lift_start) / max(args.lift_duration_s, 1e-6))
            p = s * (len(lift_poses) - 1)
            j = min(int(p), len(lift_poses) - 2)
            q_cmd[i, joint_qadr] = ((1 - (p - j)) * lift_poses[j]
                                    + (p - j) * lift_poses[j + 1])
        else:
            q_cmd[i, joint_qadr] = x_lift
            q_cmd[i, joint_qadr[:7]] = lift_hold_arm_q
    # The free cube trajectory is not replayed. Only the robot reference prefix
    # is used; cube is initialized once and then integrated dynamically.

    # Kinematic mode prescribes robot qpos. torque_pd mode instead keeps the
    # source actuators (bounded joint motors) active and tracks q_cmd with PD
    # torques while the free cube/table/contact dynamics remain unconstrained.
    if model.nu and args.control_mode == "kinematic":
        model.actuator_gainprm[:] = 0.0
        model.actuator_biasprm[:] = 0.0
        data.ctrl[:] = 0.0
    actuator_joint_ids = np.asarray(model.actuator_trnid[:, 0], dtype=int)
    actuator_joint_qadr = np.asarray(model.jnt_qposadr[actuator_joint_ids], dtype=int)
    actuator_joint_dadr = np.asarray(model.jnt_dofadr[actuator_joint_ids], dtype=int)

    data.qpos[:cube_qadr] = q_cmd[0, :cube_qadr]
    data.qpos[cube_qadr:cube_qadr + 3] = cube_center
    data.qpos[cube_qadr + 3:cube_qadr + 7] = [math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)]
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)

    robot_dof_end = cube_dadr
    n = len(times)
    sim_qpos = np.zeros((n, model.nq), dtype=np.float64)
    metrics = []
    contact_latch_time = None
    latched_hand_q = None
    per_finger_latch_times = [None, None, None]
    per_finger_latch_q = [None, None, None]
    first_contact_pause_time = None
    paused_arm_q = None
    paused_hand_q = None
    first_close_contact_time = None
    first_close_contact_hand_q = None
    close_arm_latch = None
    extra_close_active = False
    grasp_pad_centroid_offset = None
    lift_extra_fractions = [
        args.lift_extra_close_fraction if args.lift_extra_thumb_fraction is None
        else args.lift_extra_thumb_fraction,
        args.lift_extra_close_fraction if args.lift_extra_index_fraction is None
        else args.lift_extra_index_fraction,
        args.lift_extra_close_fraction if args.lift_extra_middle_fraction is None
        else args.lift_extra_middle_fraction,
    ]
    table_z = table_top_z
    initial_xy = cube_center[:2].copy()
    timestep = float(model.opt.timestep)

    def command_root_velocity(i, u):
        data.qvel[:robot_dof_end] = 0.0

    def lift_arm_target(t, start_time):
        progress = smoothstep((t - start_time) / max(args.lift_duration_s, 1e-6))
        p = progress * (len(lift_poses) - 1)
        j = min(int(p), len(lift_poses) - 2)
        frac = p - j
        return ((1 - frac) * lift_poses[j][:7] + frac * lift_poses[j + 1][:7])

    for i in range(n):
        track_phase = phase_at(float(times[i]), motion_events)
        if (args.track_cube and contact_latch_time is not None
                and times[i] >= contact_latch_time
                and track_phase in {"CONTACT_CONFIRM", "LIFT"}):
            # Retarget the prescribed arm in XY to the current free-cube pose.
            # A finite-difference fingertip-centroid Jacobian turns object drift
            # into a small arm correction; no constraint is added to the cube.
            cube_now = data.qpos[cube_qadr:cube_qadr + 3].copy()
            x_base = q_cmd[i, joint_qadr].copy()
            center0 = fingertip_centers(x_base).mean(axis=0)
            if grasp_pad_centroid_offset is None:
                grasp_pad_centroid_offset = center0 - cube_center
            center_goal = cube_now + grasp_pad_centroid_offset
            tracking_error = center_goal - center0
            if np.linalg.norm(tracking_error) > 1e-6:
                jac = np.zeros((3, 7))
                eps = 1e-4
                for j in range(7):
                    x_pert = x_base.copy()
                    x_pert[j] += eps
                    jac[:, j] = (fingertip_centers(x_pert).mean(axis=0) - center0) / eps
                dq, *_ = np.linalg.lstsq(
                    jac, args.track_gain * tracking_error, rcond=None)
                dq_norm = float(np.linalg.norm(dq))
                if dq_norm > args.track_max_dq:
                    dq *= args.track_max_dq / dq_norm
                q_cmd[i, joint_qadr[:7]] = np.clip(
                    x_base[:7] + dq, joint_limits[:7, 0], joint_limits[:7, 1])
        if first_contact_pause_time is not None and times[i] > first_contact_pause_time:
            # Dwell briefly at first contact, then resume a slow descent to the
            # final IK pose while the first contacting finger follows the face.
            settle_s = 0.30
            progress = smoothstep((times[i] - first_contact_pause_time - settle_s)
                                  / max(args.close_duration_s, 1e-6))
            if times[i] < lift_start:
                q_cmd[i, joint_qadr[:7]] = (1 - progress) * paused_arm_q + progress * x_ik[:7]
            s_close = progress
            closure_q = (1 - s_close) * paused_hand_q + s_close * x_ik[7:]
            finger_slices = (slice(7, 10), slice(10, 12), slice(12, 14))
            for fi, sl in enumerate(finger_slices):
                if per_finger_latch_q[fi] is None:
                    q_cmd[i, joint_qadr[sl]] = closure_q[sl.start - 7:sl.stop - 7]
                else:
                    q_cmd[i, joint_qadr[sl]] = per_finger_latch_q[fi]
        if (first_close_contact_time is not None
                and first_close_contact_time <= times[i] < close_end):
            # A short whole-hand dwell dissipates the first contact impulse;
            # then resume a slow coordinated close. If all pads synchronized,
            # preserve the latched three-finger pose instead.
            if contact_latch_time is not None:
                if (track_phase == "LIFT" and not all(contact_fingers)
                        and args.lift_extra_close_fraction > 0.0):
                    extra_close_active = True
                if extra_close_active:
                    extra_hand = x_ik[7:] + args.lift_extra_close_fraction * (
                        x_ik[7:] - x_open[7:])
                    q_cmd[i, joint_qadr[7:]] = np.clip(
                        extra_hand, joint_limits[7:, 0], joint_limits[7:, 1])
                else:
                    q_cmd[i, joint_qadr[7:]] = latched_hand_q
            elif times[i] < first_close_contact_time + 0.25:
                q_cmd[i, joint_qadr[7:]] = first_close_contact_hand_q
            else:
                close_s = smoothstep((times[i] - first_close_contact_time - 0.25)
                                     / max(close_end - first_close_contact_time - 0.25, 1e-6))
                p = close_s * (len(close_poses) - 1)
                j = min(int(p), len(close_poses) - 2)
                q_cmd[i, joint_qadr] = ((1 - (p - j)) * close_poses[j]
                                        + (p - j) * close_poses[j + 1])
                if args.lock_arm_after_first_touch and close_arm_latch is not None:
                    # Once the first pad has touched, stop translating the
                    # wrist/arm while the remaining fingers finish closing.
                    q_cmd[i, joint_qadr[:7]] = close_arm_latch
                # In CLOSE, latch each fingertip as soon as its own pad makes
                # contact. Otherwise the interpolated whole-hand trajectory
                # keeps driving that pad through the free cube while waiting
                # for the other two fingers to arrive.
                finger_slices = (slice(7, 10), slice(10, 12), slice(12, 14))
                if args.staged_touch_latch:
                    for fi, sl in enumerate(finger_slices):
                        if per_finger_latch_q[fi] is not None:
                            q_cmd[i, joint_qadr[sl]] = per_finger_latch_q[fi]
        if contact_latch_time is not None and track_phase in {"LIFT", "HOLD"}:
            if not all(contact_fingers) and args.lift_extra_close_fraction > 0.0:
                extra_close_active = True
            if extra_close_active:
                extra_hand = x_ik[7:].copy()
                finger_slices = (slice(7, 10), slice(10, 12), slice(12, 14))
                for fi, sl in enumerate(finger_slices):
                    hand_sl = slice(sl.start - 7, sl.stop - 7)
                    extra_hand[hand_sl] += lift_extra_fractions[fi] * (
                        x_ik[sl] - x_open[sl])
                q_cmd[i, joint_qadr[7:]] = np.clip(
                    extra_hand, joint_limits[7:, 0], joint_limits[7:, 1])
            else:
                q_cmd[i, joint_qadr[7:]] = latched_hand_q
        if i == 0:
            robot_q = q_cmd[i, :cube_qadr]
            data.qpos[:cube_qadr] = robot_q
            data.qvel[:robot_dof_end] = 0.0
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
                frame_dt = max(float(times[i] - times[i-1]), timestep)
                if args.control_mode == "kinematic":
                    data.qpos[:cube_qadr] = robot_q
                    command_root_velocity(i-1, u)
                    for jid, qa, da in zip(joint_ids, joint_qadr, joint_dadr):
                        if model.jnt_type[jid] in (mujoco.mjtJoint.mjJNT_HINGE,
                                                   mujoco.mjtJoint.mjJNT_SLIDE):
                            data.qvel[da] = (q1[qa] - q0[qa]) / frame_dt
                    data.ctrl[:] = 0.0
                else:
                    # The floating base remains fixed at the recorded standing
                    # reference; every articulated joint follows the staged
                    # reference through its model motor and contact loads.
                    data.qpos[:7] = robot_q[:7]
                    data.qvel[:6] = 0.0
                    qd_ref = (q1 - q0) / frame_dt
                    for aid, qa, da in zip(range(model.nu), actuator_joint_qadr,
                                           actuator_joint_dadr):
                        jid = int(actuator_joint_ids[aid])
                        jname = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, jid) or ""
                        hand_joint = "hand_" in jname
                        kp = args.hand_kp if hand_joint else args.arm_kp
                        kd = args.hand_kd if hand_joint else args.arm_kd
                        torque = kp * (robot_q[qa] - data.qpos[qa]) + kd * (
                            qd_ref[qa] - data.qvel[da])
                        if model.actuator_ctrllimited[aid]:
                            torque = float(np.clip(torque, *model.actuator_ctrlrange[aid]))
                        data.ctrl[aid] = torque
                mujoco.mj_forward(model, data)
                mujoco.mj_step(model, data)
            # In kinematic mode pin the complete reference pose. In motor-PD
            # mode only hold the floating base; articulated qpos/qvel must be
            # left to the actuator dynamics or the simulation silently falls
            # back to a kinematic replay between frame samples.
            if args.control_mode == "kinematic":
                data.qpos[:cube_qadr] = q_cmd[i, :cube_qadr]
                data.qvel[:robot_dof_end] = 0.0
            else:
                data.qpos[:7] = q_cmd[i, :7]
                data.qvel[:6] = 0.0
            mujoco.mj_forward(model, data)

        sim_qpos[i] = data.qpos.copy()
        cube_pos = data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "red_cube")].copy()
        cube_rot = data.geom_xmat[cube_geom_id].reshape(3, 3)
        vertical_half = float(np.sum(np.abs(cube_rot[2, :]) * model.geom_size[cube_geom_id, :3]))
        bottom_clearance = float(cube_pos[2] - vertical_half - table_z)
        contact_fingers = [False, False, False]
        finger_normal_forces = [0.0, 0.0, 0.0]
        finger_tangent_forces = [0.0, 0.0, 0.0]
        finger_vertical_forces = [0.0, 0.0, 0.0]
        finger_cube_force_z = [0.0, 0.0, 0.0]
        finger_contact_z = [float("nan")] * 3
        finger_contact_normal_z = [float("nan")] * 3
        finger_contact_x = [float("nan")] * 3
        finger_contact_y = [float("nan")] * 3
        finger_contact_friction0 = [float("nan")] * 3
        table_normal_force = 0.0
        table_contact = False
        other_cube_contacts = set()
        for ci in range(data.ncon):
            c = data.contact[ci]
            g1, g2 = int(c.geom1), int(c.geom2)
            if g1 == cube_geom_id or g2 == cube_geom_id:
                other = g2 if g1 == cube_geom_id else g1
                if other == table_geom_id and c.dist <= 0.0005:
                    table_contact = True
                    contact_force = np.zeros(6)
                    mujoco.mj_contactForce(model, data, ci, contact_force)
                    table_normal_force += abs(float(contact_force[0]))
                for fi, fg in enumerate(finger_ids):
                    if other == fg and c.dist <= 0.0005:
                        contact_fingers[fi] = True
                        contact_force = np.zeros(6)
                        mujoco.mj_contactForce(model, data, ci, contact_force)
                        finger_normal_forces[fi] += abs(float(contact_force[0]))
                        finger_tangent_forces[fi] += float(np.linalg.norm(contact_force[1:3]))
                        contact_frame = np.asarray(c.frame).reshape(3, 3)
                        world_force = contact_frame.T @ contact_force[:3]
                        finger_vertical_forces[fi] += abs(float(world_force[2]))
                        # The solver normal points from geom1 to geom2; the
                        # physical force on geom1 is opposite that direction.
                        cube_force_sign = -1.0 if g1 == cube_geom_id else 1.0
                        finger_cube_force_z[fi] += cube_force_sign * float(world_force[2])
                        finger_contact_z[fi] = float(c.pos[2])
                        finger_contact_normal_z[fi] = float(contact_frame[0, 2])
                        finger_contact_x[fi] = float(c.pos[0])
                        finger_contact_y[fi] = float(c.pos[1])
                        finger_contact_friction0[fi] = float(c.friction[0])
                if other != table_geom_id and other not in finger_ids and c.dist <= 0.0005:
                    other_cube_contacts.add(mujoco.mj_id2name(
                        model, mujoco.mjtObj.mjOBJ_GEOM, other) or f"geom_{other}")
        pad_centers = data.geom_xpos[finger_ids].copy()
        finger_clearances = [float(mujoco.mj_geomDistance(model, data, int(g), cube_geom_id,
                                                          1.0, None)) for g in finger_ids]
        cube_rot_frame = data.geom_xmat[cube_geom_id].reshape(3, 3)
        cube_roll = math.atan2(cube_rot_frame[2, 1], cube_rot_frame[2, 2])
        cube_pitch = math.asin(float(np.clip(-cube_rot_frame[2, 0], -1.0, 1.0)))
        cube_yaw_now = math.atan2(cube_rot_frame[1, 0], cube_rot_frame[0, 0])
        if (first_contact_pause_time is None and
                phase_at(float(times[i]), motion_events) == "DESCEND" and any(contact_fingers)):
            first_contact_pause_time = float(times[i])
            paused_arm_q = q_cmd[i, joint_qadr[:7]].copy()
            paused_hand_q = q_cmd[i, joint_qadr[7:]].copy()
        if (first_close_contact_time is None and close_start <= times[i] <= close_end
                and any(contact_fingers)):
            first_close_contact_time = float(times[i])
            first_close_contact_hand_q = q_cmd[i, joint_qadr[7:]].copy()
            if args.lock_arm_after_first_touch:
                close_arm_latch = q_cmd[i, joint_qadr[:7]].copy()
        if (close_start <= times[i] <= close_end or
                (first_contact_pause_time is not None and times[i] >= first_contact_pause_time) or
                (phase_at(float(times[i]), motion_events) == "LIFT" and all(contact_fingers))):
            # A finger that has made contact must stop advancing immediately;
            # otherwise its continued kinematic closure shoves/tilts the free
            # cube while the remaining pads are still approaching.
            finger_slices = (slice(7, 10), slice(10, 12), slice(12, 14))
            if close_start <= times[i] <= close_end:
                if args.staged_touch_latch:
                    for fi, sl in enumerate(finger_slices):
                        if (per_finger_latch_q[fi] is not None
                                and not contact_fingers[fi]):
                            # A finger can lose its first touch as the cube shifts
                            # under the other pads. Resume its smooth close path
                            # and re-latch only after contact is regained.
                            per_finger_latch_q[fi] = None
                            per_finger_latch_times[fi] = None
                        if contact_fingers[fi] and per_finger_latch_times[fi] is None:
                            per_finger_latch_times[fi] = float(times[i])
                            finger_qadr = joint_qadr[sl]
                            contact_q = q_cmd[i, finger_qadr].copy()
                            target_q = x_ik[sl].copy()
                            per_finger_latch_q[fi] = (
                                contact_q + args.contact_preload_fraction * (target_q - contact_q))
                            q_cmd[i + 1:, finger_qadr] = per_finger_latch_q[fi]
            elif first_contact_pause_time is not None:
                for fi, sl in enumerate(finger_slices):
                    if contact_fingers[fi] and per_finger_latch_times[fi] is None:
                        per_finger_latch_times[fi] = float(times[i])
                        finger_qadr = joint_qadr[sl]
                        per_finger_latch_q[fi] = q_cmd[i, finger_qadr].copy()
                        q_cmd[i + 1:, finger_qadr] = per_finger_latch_q[fi]
            latch_phase = phase_at(float(times[i]), motion_events)
            if (contact_latch_time is None and all(contact_fingers) and
                    (close_start <= times[i] <= close_end or latch_phase == "LIFT")):
                contact_latch_time = float(times[i])
                latched_hand_q = data.qpos[joint_qadr[7:]].copy()
                grasp_pad_centroid_offset = pad_centers.mean(axis=0) - cube_pos
                if latch_phase == "LIFT":
                    # Late but genuine dynamic recapture: preserve the arm's
                    # already-rising path instead of rewinding it to the
                    # nominal closed-pose waypoint, and hold the hand joints.
                    confirm_end = contact_latch_time + args.confirm_duration_s
                    lift_start = confirm_end + args.prelift_duration_s
                    hold_start = min(events["HOLD"], lift_start + lift_stop_after)
                    motion_events["CONTACT_CONFIRM"] = contact_latch_time
                    motion_events["PRELIFT"] = confirm_end
                    motion_events["LIFT"] = lift_start
                    motion_events["HOLD"] = hold_start
                    hold_i = int(np.searchsorted(times, hold_start, side="left"))
                    hold_i = min(hold_i, n - 1)
                    lift_hold_arm_q = q_cmd[hold_i, joint_qadr[:7]].copy()
                    q_cmd[hold_i:, joint_qadr[:7]] = lift_hold_arm_q
                    q_cmd[i + 1:, joint_qadr[7:]] = latched_hand_q
                else:
                    q_cmd[i + 1:, joint_qadr[7:]] = latched_hand_q
                    # Confirm a three-pad contact during CLOSE, then start the
                    # Cartesian lift from the actual closed-pose reference.
                    close_end = contact_latch_time
                    confirm_end = contact_latch_time + args.confirm_duration_s
                    lift_start = confirm_end + args.prelift_duration_s
                    hold_start = min(events["HOLD"], lift_start + lift_stop_after)
                    motion_events["CONTACT_CONFIRM"] = contact_latch_time
                    motion_events["PRELIFT"] = confirm_end
                    motion_events["LIFT"] = lift_start
                    motion_events["HOLD"] = hold_start
                    for future_i in range(i + 1, n):
                        if times[future_i] < confirm_end:
                            q_cmd[future_i, joint_qadr[:7]] = x_ik[:7]
                        elif times[future_i] < lift_start:
                            u = smoothstep((times[future_i] - confirm_end)
                                           / max(args.prelift_duration_s, 1e-6))
                            q_cmd[future_i, joint_qadr[:7]] = (
                                (1 - u) * x_ik[:7] + u * x_nudge[:7])
                        elif times[future_i] < hold_start:
                            q_cmd[future_i, joint_qadr[:7]] = lift_arm_target(
                                float(times[future_i]), lift_start)
                        else:
                            q_cmd[future_i, joint_qadr[:7]] = lift_arm_target(
                                hold_start, lift_start)
        slip = float(np.linalg.norm(cube_pos[:2] - initial_xy))
        joint_tracking_error = np.abs(data.qpos[joint_qadr] - q_cmd[i, joint_qadr])
        metrics.append({
            "frame": i, "time_s": float(times[i]), "phase": phase_at(float(times[i]), motion_events),
            "cube_x_m": float(cube_pos[0]), "cube_y_m": float(cube_pos[1]),
            "cube_z_m": float(cube_pos[2]), "cube_bottom_clearance_m": bottom_clearance,
            "cube_slip_from_start_xy_m": slip,
            "right_arm_tracking_error_max_rad": float(np.max(joint_tracking_error[:7])),
            "right_hand_tracking_error_max_rad": float(np.max(joint_tracking_error[7:])),
            "thumb_contact": int(contact_fingers[0]), "index_contact": int(contact_fingers[1]),
            "middle_contact": int(contact_fingers[2]), "table_support_contact": int(table_contact),
            "other_cube_contacts": ";".join(sorted(other_cube_contacts)),
            "thumb_clearance_m": finger_clearances[0],
            "index_clearance_m": finger_clearances[1],
            "middle_clearance_m": finger_clearances[2],
            "thumb_normal_force_N": finger_normal_forces[0],
            "index_normal_force_N": finger_normal_forces[1],
            "middle_normal_force_N": finger_normal_forces[2],
            "thumb_tangent_force_N": finger_tangent_forces[0],
            "index_tangent_force_N": finger_tangent_forces[1],
            "middle_tangent_force_N": finger_tangent_forces[2],
            "thumb_vertical_force_N": finger_vertical_forces[0],
            "index_vertical_force_N": finger_vertical_forces[1],
            "middle_vertical_force_N": finger_vertical_forces[2],
            "thumb_force_on_cube_z_N": finger_cube_force_z[0],
            "index_force_on_cube_z_N": finger_cube_force_z[1],
            "middle_force_on_cube_z_N": finger_cube_force_z[2],
            "thumb_contact_z_m": finger_contact_z[0],
            "index_contact_z_m": finger_contact_z[1],
            "middle_contact_z_m": finger_contact_z[2],
            "thumb_contact_normal_z": finger_contact_normal_z[0],
            "index_contact_normal_z": finger_contact_normal_z[1],
            "middle_contact_normal_z": finger_contact_normal_z[2],
            "thumb_contact_x_m": finger_contact_x[0],
            "index_contact_x_m": finger_contact_x[1],
            "middle_contact_x_m": finger_contact_x[2],
            "thumb_contact_y_m": finger_contact_y[0],
            "index_contact_y_m": finger_contact_y[1],
            "middle_contact_y_m": finger_contact_y[2],
            "thumb_contact_friction0": finger_contact_friction0[0],
            "index_contact_friction0": finger_contact_friction0[1],
            "middle_contact_friction0": finger_contact_friction0[2],
            "table_normal_force_N": table_normal_force,
            "cube_vertical_velocity_m_s": float(data.qvel[cube_dadr + 2]),
            "cube_constraint_vertical_N": float(data.qfrc_constraint[cube_dadr + 2]),
            "cube_roll_rad": cube_roll, "cube_pitch_rad": cube_pitch,
            "cube_yaw_rad": cube_yaw_now,
            **{f"{finger}_{axis}_m": float(pad_centers[j, a])
               for j, finger in enumerate(("thumb_pad", "index_pad", "middle_pad"))
               for a, axis in enumerate(("x", "y", "z"))},
            "ncon": int(data.ncon),
        })

    hold_end = min(hold_start + 2.0, events.get("RELEASE", hold_start + 2.0))
    hold = [m for m in metrics if hold_start <= m["time_s"] <= hold_end]
    lift_window = [m for m in metrics if lift_start <= m["time_s"] <= hold_end]
    contact_rate = {f: float(np.mean([row[f + "_contact"] for row in hold])) if hold else 0.0
                    for f in ("thumb", "index", "middle")}
    hold_min_clear = min((row["cube_bottom_clearance_m"] for row in hold), default=-1.0)
    max_clearance_all = max((row["cube_bottom_clearance_m"] for row in metrics), default=-1.0)
    max_xy_slip_all = max((row["cube_slip_from_start_xy_m"] for row in metrics), default=0.0)
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
        "lift_actual_pad_centers_world_m": lift_actual_centers.tolist(),
        "lift_pad_target_error_m": lift_pad_target_errors.tolist(),
        "hover_ik_success_flag": bool(hover_ik.success), "hover_ik_nfev": int(hover_ik.nfev),
        "open_ik_success_flag": bool(open_ik.success), "open_ik_nfev": int(open_ik.nfev),
        "open_finger_joint_delta_rad": {name: float(v) for name, v in
                                         zip(ARM_HAND_JOINTS[7:], x_open[7:] - x_ik[7:])},
        "open_targets_world_m": open_targets.tolist(),
        "open_actual_pad_centers_world_m": open_actual_centers.tolist(),
        "open_pad_target_error_m": open_pad_target_errors.tolist(),
        "close_waypoint_max_center_error_m": close_pose_errors,
        "phase_schedule_s": motion_events,
        "three_finger_contact_latched_at_s": contact_latch_time,
        "first_contact_descent_pause_at_s": first_contact_pause_time,
        "first_close_contact_dwell_at_s": first_close_contact_time,
        "per_finger_contact_latched_at_s": {
            finger: per_finger_latch_times[i]
            for i, finger in enumerate(("thumb", "index", "middle"))
        },
        "latched_hand_joint_values_rad": None if latched_hand_q is None else latched_hand_q.tolist(),
        "squeeze_mm": args.squeeze_mm,
        "per_finger_squeeze_mm": dict(zip(("thumb", "index", "middle"),
                                           map(float, finger_squeeze))),
        "grip_height_offset_mm": args.grip_height_offset_mm,
        "open_gap_mm": args.open_gap_mm,
        "close_duration_s": args.close_duration_s,
        "confirm_duration_s": args.confirm_duration_s,
        "lift_duration_s": args.lift_duration_s,
        "lift_stop_after_s": args.lift_stop_after_s,
        "prelift_nudge_mm": args.prelift_nudge_mm,
        "prelift_duration_s": args.prelift_duration_s,
        "pad_friction_coefficient": args.pad_friction,
        "pad_adhesion_per_contact_N": args.pad_adhesion_n,
        "cube_friction_coefficient": args.cube_friction,
        "finger_geom_friction": model.geom_friction[finger_ids].tolist(),
        "cube_geom_friction": model.geom_friction[cube_geom_id].tolist(),
        "finger_geom_priority": model.geom_priority[finger_ids].tolist(),
        "cube_geom_priority": int(model.geom_priority[cube_geom_id]),
        "hover_targets_world_m": hover_targets.tolist(),
        "descent_waypoint_heights_m": [0.075] + descent_heights.tolist(),
        "lift_waypoint_heights_m": [0.0] + lift_heights.tolist(),
        "lift_targets_world_m": lift_targets.tolist(),
        "lift_joint_delta_from_grasp_rad": {name: float(v) for name, v in zip(ARM_HAND_JOINTS, x_lift - x_ik)},
        "ik_joint_delta_rad": {name: float(v) for name, v in zip(ARM_HAND_JOINTS, delta)},
        "hold_window_s": [hold_start, hold_end], "hold_frames": len(hold),
        "hold_contact_rate_each": contact_rate,
        "hold_min_cube_bottom_clearance_m": float(hold_min_clear),
        "max_cube_bottom_clearance_overall_m": float(max_clearance_all),
        "max_xy_slip_from_initial_overall_m": float(max_xy_slip_all),
        "max_right_arm_tracking_error_rad": float(max(
            row["right_arm_tracking_error_max_rad"] for row in metrics)),
        "max_right_hand_tracking_error_rad": float(max(
            row["right_hand_tracking_error_max_rad"] for row in metrics)),
        "hold_max_xy_slip_from_start_m": float(hold_slip),
        "hold_table_support_frames": int(table_support_frames),
        "gates": gates,
        "physics_scope": ("MuJoCo gravity/table/cube/finger contact; no weld; robot qpos prescribed kinematically"
                          if args.control_mode == "kinematic" else
                          "MuJoCo gravity/table/cube/finger contact; no weld; robot joints tracked by bounded motor PD torques; floating base fixed"),
        "cube_xy_tracking_feedback_enabled": bool(args.track_cube),
        "cube_xy_tracking_gain": args.track_gain,
        "cube_xy_tracking_max_joint_delta_rad": args.track_max_dq,
        "lift_extra_close_fraction": args.lift_extra_close_fraction,
        "lift_extra_finger_fractions": dict(zip(
            ("thumb", "index", "middle"), map(float, lift_extra_fractions))),
        "contact_preload_fraction": args.contact_preload_fraction,
        "lock_arm_after_first_touch": args.lock_arm_after_first_touch,
        "staged_touch_latch": args.staged_touch_latch,
        "control_mode": args.control_mode,
        "arm_kp_Nm_per_rad": args.arm_kp,
        "arm_kd_Nm_s_per_rad": args.arm_kd,
        "hand_kp_Nm_per_rad": args.hand_kp,
        "hand_kd_Nm_s_per_rad": args.hand_kd,
        "cube_xy_tracking_feedback_mode": "after_synchronized_three_finger_latch_only",
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
            hud2 = (f"sim t={times[idx]:.2f}s | {phase_at(float(times[idx]), motion_events)} | "
                    f"cube bottom clearance={metrics[idx]['cube_bottom_clearance_m']*1000:.0f} mm | "
                    f"playback ~{args.playback_speed_label:.1f}x")
            cv2.putText(frame, hud1, (18, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 1, cv2.LINE_AA)
            cv2.putText(frame, hud2, (18, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220,235,247), 1, cv2.LINE_AA)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        if idx in {0, align_i, int(np.argmin(abs(times - motion_events["CLOSE"]))),
                   int(np.argmin(abs(times - motion_events["LIFT"]))),
                   int(np.argmin(abs(times - hold_start))), n - 1}:
            imageio.imwrite(out / "keyframes" / f"frame_{idx:04d}_{phase_at(float(times[idx]), motion_events)}.png", frame)
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
