import argparse
import hashlib
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mujoco
import numpy as np
import yaml

from adapters.sonic_action_adapter import (
    DEFAULT_ANGLES,
    STAND_INIT_HEIGHT,
    SonicActionAdapter,
)
from adapters.sonic_encoder_adapter import SonicEncoderAdapter
from adapters.sonic_policy_adapter import SonicPolicyAdapter
from motion_adapter import (
    DEFAULT_G1_MODEL_XML,
    MUJOCO_G1_29_JOINT_NAMES,
    add_motion_arguments,
    load_motion_runtime,
    quaternion_yaw,
    write_physical_grasp_baseline,
)
from policies.sonic_policy import SonicPolicy


RIGHT_ARM = np.arange(22, 29)
RIGHT_HAND_ACTUATORS = np.arange(36, 43)
GRASP_OFFSET = np.array([0.094, 0.099, 0.006], dtype=np.float64)
TASK_POSITION_BIAS = np.zeros(3, dtype=np.float64)

# Fixed-scene grasp keyframes. The grasp point is the measured center between
# the thumb and index/middle fingers, not the wrist body origin.
RIGHT_ARM_GRASP = np.array(
    [-1.046944, -0.642793, -1.911197, 1.787889,
     -1.653604, 1.326327, 0.335080],
    dtype=np.float64,
)
RIGHT_ARM_SAFE = np.array(
    [-1.363069, -0.615202, 2.050898, 0.222550,
     0.360051, 1.311507, 1.614430],
    dtype=np.float64,
)
RIGHT_ARM_HIGH = np.array(
    [-1.123446, -0.928874, -2.164452, 2.069049,
     -1.405235, 1.603174, 0.097037],
    dtype=np.float64,
)
RIGHT_ARM_LIFT = RIGHT_ARM_HIGH.copy()
RIGHT_HAND_OPEN = np.array(
    [0.0, -0.70, -2.00, 1.40, 0.08, 1.40, 0.08],
    dtype=np.float64,
)
RIGHT_HAND_CLOSED = np.array(
    [0.0, -0.60, -0.425, 1.40, 0.08, 1.40, 0.08],
    dtype=np.float64,
)

TABLE_TOP_Z = 0.725


def smoothstep(value):
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def blend(start, end, value):
    return start + smoothstep(value) * (end - start)


def load_config(path):
    with open(path, "r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def actuator_state_indices(model, actuator_indices):
    joint_ids = np.asarray(model.actuator_trnid[actuator_indices, 0], dtype=int)
    return (
        np.asarray(model.jnt_qposadr[joint_ids], dtype=int),
        np.asarray(model.jnt_dofadr[joint_ids], dtype=int),
    )


def grasp_pose(data, wrist_body_id):
    wrist_rotation = data.xmat[wrist_body_id].reshape(3, 3)
    position = data.xpos[wrist_body_id] + wrist_rotation @ GRASP_OFFSET
    return position, wrist_rotation


def corrected_arm_target(
    model,
    data,
    reference_data,
    wrist_body_id,
    arm_qpos_adr,
    arm_dof_adr,
    nominal_target,
    position_bias,
):
    reference_data.qpos[arm_qpos_adr] = nominal_target
    mujoco.mj_forward(model, reference_data)
    desired_position, desired_rotation = grasp_pose(
        reference_data, wrist_body_id
    )
    desired_position = desired_position + position_bias
    position, rotation = grasp_pose(data, wrist_body_id)

    jac_pos = np.zeros((3, model.nv))
    jac_rot = np.zeros((3, model.nv))
    mujoco.mj_jac(
        model, data, jac_pos, jac_rot, position, wrist_body_id
    )
    rotation_error = 0.5 * sum(
        np.cross(rotation[:, axis], desired_rotation[:, axis])
        for axis in range(3)
    )
    orientation_weight = 0.18
    jacobian = np.vstack(
        (
            jac_pos[:, arm_dof_adr],
            orientation_weight * jac_rot[:, arm_dof_adr],
        )
    )
    error = np.concatenate(
        (
            desired_position - position,
            orientation_weight * rotation_error,
        )
    )
    damping = 0.04
    delta = jacobian.T @ np.linalg.solve(
        jacobian @ jacobian.T + damping**2 * np.eye(6), error
    )
    delta += 0.04 * (nominal_target - data.qpos[arm_qpos_adr])
    delta = np.clip(delta, -0.12, 0.12)
    return data.qpos[arm_qpos_adr] + delta


def tracked_arm_target(
    model,
    data,
    wrist_body_id,
    arm_qpos_adr,
    arm_dof_adr,
    desired_position,
    _desired_rotation,
):
    position, _ = grasp_pose(data, wrist_body_id)
    jac_pos = np.zeros((3, model.nv))
    jac_rot = np.zeros((3, model.nv))
    mujoco.mj_jac(
        model, data, jac_pos, jac_rot, position, wrist_body_id
    )
    jacobian = jac_pos[:, arm_dof_adr]
    error = desired_position - position
    damping = 0.02
    delta = jacobian.T @ np.linalg.solve(
        jacobian @ jacobian.T + damping**2 * np.eye(3), error
    )
    delta = np.clip(delta, -0.12, 0.12)
    return data.qpos[arm_qpos_adr] + delta


def grasp_phase(time_s, close_start, lift_start, lift_duration):
    if time_s < 1.0:
        return "settle"
    if time_s < 4.0:
        return "raise"
    if time_s < 7.0:
        return "move_over"
    if time_s < 9.0:
        return "pregrasp"
    if time_s < close_start:
        return "descend"
    if time_s < lift_start:
        return "close"
    if time_s < lift_start + lift_duration:
        return "lift"
    return "hold"


def generated_grasp_phase(
    time_s, close_start, lift_start, lift_duration
):
    if time_s < close_start:
        return "motion"
    if time_s < lift_start:
        return "close"
    if time_s < lift_start + lift_duration:
        return "lift"
    return "hold"


def keyframe_arm_target(
    time_s,
    close_start,
    lift_start,
    lift_duration,
):
    arm_default = DEFAULT_ANGLES[RIGHT_ARM]
    if time_s < 1.0:
        return arm_default
    if time_s < 4.0:
        return blend(arm_default, RIGHT_ARM_SAFE, (time_s - 1.0) / 3.0)
    if time_s < 7.0:
        return blend(RIGHT_ARM_SAFE, RIGHT_ARM_HIGH, (time_s - 4.0) / 3.0)
    if time_s < 9.0:
        return RIGHT_ARM_HIGH
    if time_s < close_start:
        return blend(
            RIGHT_ARM_HIGH,
            RIGHT_ARM_GRASP,
            (time_s - 9.0) / (close_start - 9.0),
        )
    if time_s < lift_start:
        return RIGHT_ARM_GRASP
    if time_s < lift_start + lift_duration:
        return blend(
            RIGHT_ARM_GRASP,
            RIGHT_ARM_HIGH,
            (time_s - lift_start) / lift_duration,
        )
    return RIGHT_ARM_HIGH


def grasp_targets(
    time_s,
    no_grip,
    open_hand_target,
    closed_hand_target,
    close_start,
    close_duration,
    thumb_delay,
    lift_start,
    lift_duration,
    *,
    generated_motion,
):
    phase_fn = generated_grasp_phase if generated_motion else grasp_phase
    phase = phase_fn(time_s, close_start, lift_start, lift_duration)
    arm = None
    if not generated_motion:
        arm = keyframe_arm_target(
            time_s,
            close_start,
            lift_start,
            lift_duration,
        )

    if no_grip or time_s < close_start:
        hand = open_hand_target
    else:
        hand = blend(
            open_hand_target,
            closed_hand_target,
            (time_s - close_start) / close_duration,
        )
        hand[:3] = blend(
            open_hand_target[:3],
            closed_hand_target[:3],
            (time_s - close_start - thumb_delay) / close_duration,
        )
    return phase, arm, hand


def set_initial_state(model, data, open_hand_target=RIGHT_HAND_OPEN):
    data.qpos[:7] = [0.0, 0.0, STAND_INIT_HEIGHT, 1.0, 0.0, 0.0, 0.0]
    for actuator_id, angle in enumerate(DEFAULT_ANGLES):
        joint_id = model.actuator_trnid[actuator_id, 0]
        data.qpos[model.jnt_qposadr[joint_id]] = angle
    for actuator_id in range(29, 43):
        joint_id = model.actuator_trnid[actuator_id, 0]
        data.qpos[model.jnt_qposadr[joint_id]] = 0.0
    for actuator_id, angle in zip(RIGHT_HAND_ACTUATORS, open_hand_target):
        joint_id = model.actuator_trnid[actuator_id, 0]
        data.qpos[model.jnt_qposadr[joint_id]] = angle
    mujoco.mj_forward(model, data)


def right_hand_contact_count(model, data, cube_geom_id, right_hand_body_ids):
    count = 0
    for contact_index in range(data.ncon):
        contact = data.contact[contact_index]
        geom1 = int(contact.geom1)
        geom2 = int(contact.geom2)
        if geom1 == cube_geom_id:
            other_body = int(model.geom_bodyid[geom2])
        elif geom2 == cube_geom_id:
            other_body = int(model.geom_bodyid[geom1])
        else:
            continue
        if other_body in right_hand_body_ids:
            count += 1
    return count


def build_right_hand_body_ids(model):
    result = set()
    for body_id in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id)
        if name and name.startswith("right_hand_"):
            result.add(body_id)
    return result


def stabilize_base(data, target_position, target_quaternion):
    rotation_error = np.zeros(3)
    mujoco.mju_subQuat(
        rotation_error, target_quaternion, np.asarray(data.qpos[3:7])
    )
    data.qfrc_applied[:3] = (
        1200.0 * (target_position - data.qpos[:3])
        - 120.0 * data.qvel[:3]
    )
    data.qfrc_applied[3:6] = (
        500.0 * rotation_error - 40.0 * data.qvel[3:6]
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/sonic_g1.yaml")
    parser.add_argument("--scene", default="g1/scene_grasp_hand.xml")
    parser.add_argument("--duration", type=float, default=18.0)
    parser.add_argument("--offscreen", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--out-dir", default="renders_grasp")
    parser.add_argument("--render-every", type=int, default=25)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--no-grip", action="store_true")
    parser.add_argument(
        "--task-bias",
        type=float,
        nargs=3,
        default=TASK_POSITION_BIAS.tolist(),
        metavar=("X", "Y", "Z"),
    )
    parser.add_argument("--pregrasp-height", type=float, default=0.0)
    parser.add_argument("--descent-duration", type=float, default=2.0)
    parser.add_argument("--descent-settle", type=float, default=0.0)
    parser.add_argument("--grasp-descent", type=float, default=0.0)
    parser.add_argument("--grasp-descent-start", type=float, default=10.0)
    parser.add_argument("--grasp-descent-duration", type=float, default=2.0)
    parser.add_argument(
        "--hand-open",
        type=float,
        nargs=7,
        default=RIGHT_HAND_OPEN.tolist(),
    )
    parser.add_argument(
        "--hand-closed",
        type=float,
        nargs=7,
        default=RIGHT_HAND_CLOSED.tolist(),
    )
    parser.add_argument("--close-duration", type=float, default=2.0)
    parser.add_argument("--close-start", type=float, default=12.0)
    parser.add_argument("--thumb-delay", type=float, default=0.0)
    parser.add_argument("--lift-start", type=float, default=14.0)
    parser.add_argument("--lift-duration", type=float, default=3.0)
    parser.add_argument("--lift-height", type=float, default=0.10)
    parser.add_argument("--finger-torque-limit", type=float, default=1.0)
    parser.add_argument(
        "--finger-kp", type=float, nargs=2, default=(4.0, 2.0)
    )
    parser.add_argument("--allow-failure", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--free-base", action="store_true")
    parser.add_argument("--no-cube-tracking", action="store_true")
    parser.add_argument(
        "--export-baseline-csv",
        help="write successful keyframe root + 29 body qpos at policy rate",
    )
    parser.add_argument(
        "--export-baseline-manifest",
        help="write provenance and physical acceptance metrics as JSON",
    )
    parser.add_argument(
        "--direct-arm", dest="direct_arm", action="store_true", default=True
    )
    parser.add_argument(
        "--online-arm", dest="direct_arm", action="store_false"
    )
    add_motion_arguments(parser)
    args = parser.parse_args()
    if args.offscreen and args.headless:
        parser.error("--offscreen and --headless are mutually exclusive")
    if min(
        args.close_duration,
        args.descent_duration,
        args.grasp_descent_duration,
        args.lift_duration,
    ) <= 0:
        parser.error("phase durations must be positive")
    if args.descent_settle < 0:
        parser.error("--descent-settle must be non-negative")
    if args.thumb_delay < 0:
        parser.error("--thumb-delay must be non-negative")
    if args.motion_source is None and args.close_start <= 9.0:
        parser.error(
            "--close-start must be greater than 9.0 in keyframe mode"
        )
    if args.motion_source is not None and args.close_start < 0.0:
        parser.error(
            "--close-start must be non-negative in generated-motion mode"
        )
    if args.lift_start < args.close_start:
        parser.error("--lift-start must not precede --close-start")
    if args.finger_torque_limit <= 0:
        parser.error("--finger-torque-limit must be positive")
    if min(args.finger_kp) <= 0:
        parser.error("--finger-kp values must be positive")
    export_paths = (
        args.export_baseline_csv,
        args.export_baseline_manifest,
    )
    if any(export_paths) and not all(export_paths):
        parser.error(
            "--export-baseline-csv and --export-baseline-manifest "
            "must be provided together"
        )
    if any(export_paths) and args.motion_source is not None:
        parser.error("baseline export is only supported in keyframe mode")
    if any(export_paths) and args.no_grip:
        parser.error("baseline export is not supported with --no-grip")

    task_position_bias = np.asarray(args.task_bias, dtype=np.float64)
    open_hand_target = np.asarray(args.hand_open, dtype=np.float64)
    closed_hand_target = np.asarray(args.hand_closed, dtype=np.float64)

    cfg = load_config(args.config)
    model = mujoco.MjModel.from_xml_path(args.scene)
    finger_actuators = RIGHT_HAND_ACTUATORS[3:]
    finger_joint_ids = np.asarray(
        model.actuator_trnid[finger_actuators, 0], dtype=int
    )
    model.actuator_ctrlrange[finger_actuators] = (
        -args.finger_torque_limit,
        args.finger_torque_limit,
    )
    model.jnt_actfrcrange[finger_joint_ids] = (
        -args.finger_torque_limit,
        args.finger_torque_limit,
    )
    data = mujoco.MjData(model)
    set_initial_state(model, data, open_hand_target)

    if (model.nq, model.nv, model.nu) != (57, 55, 43):
        raise ValueError(
            f"unexpected grasp model dimensions: nq={model.nq}, nv={model.nv}, nu={model.nu}"
        )

    policy_hz = cfg["control"]["policy_hz"]
    try:
        motion_runtime = load_motion_runtime(
            args,
            target_fps=policy_hz,
            target_root_pos=data.qpos[:3],
            target_heading=quaternion_yaw(data.qpos[3:7]),
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    generated_motion = motion_runtime is not None
    control_mode = (
        "generated-motion" if generated_motion else "keyframe"
    )
    reference_data = None
    if not generated_motion:
        reference_data = mujoco.MjData(model)
        set_initial_state(model, reference_data, open_hand_target)

    policy = SonicPolicy(cfg)
    encoder_adapter = SonicEncoderAdapter(
        cfg,
        trajectory=(
            motion_runtime.trajectory if motion_runtime is not None else None
        ),
        motion_start=(
            motion_runtime.motion_start if motion_runtime is not None else 0.0
        ),
        motion_speed=(
            motion_runtime.motion_speed if motion_runtime is not None else 1.0
        ),
    )
    policy_adapter = SonicPolicyAdapter(cfg, model)
    action_adapter = SonicActionAdapter(cfg, model)
    print(f"[INFO] control_mode={control_mode}")
    if motion_runtime is not None:
        print(f"[INFO] {motion_runtime.startup_log_line()}")

    hand_qpos_adr, hand_dof_adr = actuator_state_indices(
        model, RIGHT_HAND_ACTUATORS
    )
    body_qpos_adr, _ = actuator_state_indices(model, np.arange(29))
    arm_qpos_adr, _ = actuator_state_indices(model, RIGHT_ARM)
    _, arm_dof_adr = actuator_state_indices(model, RIGHT_ARM)
    arm_kp = np.array([55.0, 55.0, 45.0, 45.0, 18.0, 18.0, 18.0])
    arm_kd = np.array([3.0, 3.0, 2.5, 2.5, 1.2, 1.2, 1.2])
    arm_ctrlrange = np.asarray(model.actuator_ctrlrange[RIGHT_ARM])
    hand_kp = np.array(
        [4.0, 1.8, 1.2, args.finger_kp[0], args.finger_kp[1],
         args.finger_kp[0], args.finger_kp[1]]
    )
    hand_kd = np.array([0.10, 0.07, 0.05, 0.06, 0.05, 0.06, 0.05])
    hand_ctrlrange = np.asarray(model.actuator_ctrlrange[RIGHT_HAND_ACTUATORS])

    cube_body_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_BODY, "red_cube"
    )
    wrist_body_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_BODY, "right_wrist_yaw_link"
    )
    cube_geom_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_GEOM, "red_cube_geom"
    )
    cube_half_height = float(model.geom_size[cube_geom_id, 2])
    fingertip_geom_ids = {
        name: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        for name in (
            "right_thumb_fingertip",
            "right_index_fingertip",
            "right_middle_fingertip",
        )
        if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name) >= 0
    }
    right_hand_body_ids = build_right_hand_body_ids(model)
    for geom_id in range(model.ngeom):
        if int(model.geom_bodyid[geom_id]) in right_hand_body_ids:
            model.geom_contype[geom_id] = 0
            model.geom_conaffinity[geom_id] = 0
    for geom_id in fingertip_geom_ids.values():
        model.geom_contype[geom_id] = 2
        model.geom_conaffinity[geom_id] = 0
    model.geom_contype[cube_geom_id] = 1
    model.geom_conaffinity[cube_geom_id] = 3
    cube_initial_pos = data.xpos[cube_body_id].copy()
    base_target_position = data.qpos[:3].copy()
    base_target_quaternion = data.qpos[3:7].copy()

    control_every = max(
        1, int(round((1.0 / policy_hz) / model.opt.timestep))
    )
    max_steps = int(round(args.duration / model.opt.timestep))
    last_action = np.zeros(29, dtype=np.float32)
    hand_target = open_hand_target.copy()
    arm_target = (
        None
        if generated_motion
        else DEFAULT_ANGLES[RIGHT_ARM].copy()
    )
    phase = "settle"
    max_cube_z = float(cube_initial_pos[2])
    max_contacts = 0
    max_contact_bodies = 0
    contact_bodies = set()
    max_normal_force = 0.0
    best_contact_force = -1.0
    best_contact_snapshot = []
    min_fingertip_distance = {
        name: float("inf") for name in fingertip_geom_ids
    }
    lift_contact_steps = 0
    phase_changes = []
    cube_tracking_offset = np.zeros(3, dtype=np.float64)
    lift_start_position = None
    lift_start_rotation = None
    desired_lift_position = None
    fixed_arm_override_count = 0
    fixed_arm_pd_write_count = 0
    reference_window_hashes = []
    reference_window_change_count = 0
    previous_reference_window_hash = None
    action_hashes = []
    baseline_frames = []

    renderer = None
    viewer = None
    frame_index = 0
    out_dir = Path(args.out_dir)
    if args.offscreen:
        from PIL import Image

        out_dir.mkdir(parents=True, exist_ok=True)
        renderer = mujoco.Renderer(model, height=args.height, width=args.width)
    elif not args.headless:
        from mujoco import viewer as mj_viewer

        viewer = mj_viewer.launch_passive(model, data)

    for step in range(max_steps):
        time_s = step * model.opt.timestep
        new_phase, arm_nominal, hand_target = grasp_targets(
            time_s,
            args.no_grip,
            open_hand_target,
            closed_hand_target,
            args.close_start,
            args.close_duration,
            args.thumb_delay,
            args.lift_start,
            args.lift_duration,
            generated_motion=generated_motion,
        )
        if generated_motion and arm_nominal is not None:
            raise RuntimeError(
                "generated-motion mode produced a fixed arm target"
            )
        if new_phase != phase or step == 0:
            phase = new_phase
            phase_changes.append((time_s, phase))
            mujoco.mj_forward(model, data)
            grasp_center, _ = grasp_pose(data, wrist_body_id)
            if phase == "lift" and not generated_motion:
                lift_start_position, lift_start_rotation = grasp_pose(
                    data, wrist_body_id
                )
                lift_start_position = lift_start_position.copy()
                lift_start_rotation = lift_start_rotation.copy()
            if not args.quiet:
                if generated_motion:
                    arm_status = "arm_reference=sonic"
                else:
                    arm_status = (
                        "arm_error_max="
                        f"{np.max(np.abs(data.qpos[arm_qpos_adr] - arm_nominal)):.4f}"
                    )
                print(
                    f"[PHASE] t={time_s:.2f}s {phase} "
                    f"base_pos={np.round(data.qpos[:3], 4).tolist()} "
                    f"base_quat={np.round(data.qpos[3:7], 4).tolist()} "
                    f"grasp_center={np.round(grasp_center, 4).tolist()} "
                    f"cube={np.round(data.xpos[cube_body_id], 4).tolist()} "
                    f"{arm_status} "
                    f"hand_q={np.round(data.qpos[hand_qpos_adr], 3).tolist()}"
                )

        if step % control_every == 0:
            encoder_obs = encoder_adapter.build(data)
            token_state = policy.encode(encoder_obs)
            policy_obs, _ = policy_adapter.build(data, token_state, last_action)
            raw_action = policy.act(policy_obs, token_state=token_state)
            action_hashes.append(
                hashlib.sha256(
                    np.asarray(raw_action, dtype=np.float32).tobytes()
                ).hexdigest()
            )
            action_adapter.set_action(raw_action)
            if generated_motion:
                window_hash = hashlib.sha256(
                    encoder_adapter.last_window.flatten().tobytes()
                ).hexdigest()
                reference_window_hashes.append(window_hash)
                if (
                    previous_reference_window_hash is not None
                    and window_hash != previous_reference_window_hash
                ):
                    reference_window_change_count += 1
                previous_reference_window_hash = window_hash
            else:
                bias_scale = smoothstep((time_s - 1.0) / 2.0)
                position_bias = bias_scale * task_position_bias
                position_bias = position_bias.copy()
                if (
                    not args.no_cube_tracking
                    and args.close_start <= time_s < args.lift_start
                ):
                    cube_tracking_offset[:2] = (
                        data.xpos[cube_body_id, :2] - cube_initial_pos[:2]
                    )
                position_bias += cube_tracking_offset
                if 3.0 <= time_s < args.close_start:
                    descent_end = args.close_start - args.descent_settle
                    descent_start = descent_end - args.descent_duration
                    position_bias[2] += args.pregrasp_height * (
                        1.0
                        - smoothstep(
                            (time_s - descent_start) / args.descent_duration
                        )
                    )
                if time_s >= args.grasp_descent_start:
                    position_bias[2] -= args.grasp_descent * smoothstep(
                        (time_s - args.grasp_descent_start)
                        / args.grasp_descent_duration
                    )
                if time_s >= args.lift_start:
                    position_bias[2] += args.lift_height * smoothstep(
                        (time_s - args.lift_start) / args.lift_duration
                    )
                if args.direct_arm:
                    arm_target = arm_nominal.copy()
                elif phase in ("lift", "hold"):
                    lift_progress = smoothstep(
                        (time_s - args.lift_start) / args.lift_duration
                    )
                    desired_lift_position = (
                        lift_start_position
                        + np.array(
                            [0.0, 0.0, args.lift_height * lift_progress]
                        )
                    )
                    arm_target = tracked_arm_target(
                        model,
                        data,
                        wrist_body_id,
                        arm_qpos_adr,
                        arm_dof_adr,
                        desired_lift_position,
                        lift_start_rotation,
                    )
                else:
                    arm_target = corrected_arm_target(
                        model,
                        data,
                        reference_data,
                        wrist_body_id,
                        arm_qpos_adr,
                        arm_dof_adr,
                        arm_nominal,
                        position_bias,
                    )
                action_adapter.override_targets(RIGHT_ARM, arm_target)
                fixed_arm_override_count += 1

            last_action = raw_action.copy()

        action_adapter.step_pd(data)
        if generated_motion:
            data.xfrc_applied[wrist_body_id] = 0.0
        else:
            arm_q = np.asarray(data.qpos[arm_qpos_adr])
            arm_dq = np.asarray(data.qvel[arm_dof_adr])
            arm_tau = arm_kp * (arm_target - arm_q) - arm_kd * arm_dq
            if (
                not args.direct_arm
                and phase in ("lift", "hold")
                and desired_lift_position is not None
            ):
                grasp_center, _ = grasp_pose(data, wrist_body_id)
                jac_pos = np.zeros((3, model.nv))
                jac_rot = np.zeros((3, model.nv))
                mujoco.mj_jac(
                    model,
                    data,
                    jac_pos,
                    jac_rot,
                    grasp_center,
                    wrist_body_id,
                )
                grasp_velocity = jac_pos @ data.qvel
                task_force = (
                    np.array([500.0, 500.0, 350.0])
                    * (desired_lift_position - grasp_center)
                    - np.array([40.0, 40.0, 30.0]) * grasp_velocity
                )
                task_force = np.clip(task_force, -80.0, 80.0)
                data.xfrc_applied[wrist_body_id, :3] = task_force
                arm_tau += jac_pos[:, arm_dof_adr].T @ task_force
            else:
                data.xfrc_applied[wrist_body_id] = 0.0
            data.ctrl[RIGHT_ARM] = np.clip(
                arm_tau, arm_ctrlrange[:, 0], arm_ctrlrange[:, 1]
            )
            fixed_arm_pd_write_count += 1
        hand_q = np.asarray(data.qpos[hand_qpos_adr])
        hand_dq = np.asarray(data.qvel[hand_dof_adr])
        hand_tau = hand_kp * (hand_target - hand_q) - hand_kd * hand_dq
        data.ctrl[RIGHT_HAND_ACTUATORS] = np.clip(
            hand_tau, hand_ctrlrange[:, 0], hand_ctrlrange[:, 1]
        )
        if not args.free_base:
            stabilize_base(
                data, base_target_position, base_target_quaternion
            )

        mujoco.mj_step(model, data)
        if args.export_baseline_csv and step % control_every == 0:
            baseline_frames.append(
                np.concatenate(
                    (
                        np.asarray(data.qpos[:7], dtype=np.float64),
                        np.asarray(data.qpos[body_qpos_adr], dtype=np.float64),
                    )
                )
            )

        for name, geom_id in fingertip_geom_ids.items():
            distance = mujoco.mj_geomDistance(
                model, data, cube_geom_id, geom_id, 1.0, None
            )
            min_fingertip_distance[name] = min(
                min_fingertip_distance[name], float(distance)
            )

        contact_count = right_hand_contact_count(
            model, data, cube_geom_id, right_hand_body_ids
        )
        contact_snapshot = []
        contact_force_sum = 0.0
        current_contact_bodies = set()
        for contact_index in range(data.ncon):
            contact = data.contact[contact_index]
            geom1 = int(contact.geom1)
            geom2 = int(contact.geom2)
            if cube_geom_id not in (geom1, geom2):
                continue
            other_geom = geom2 if geom1 == cube_geom_id else geom1
            other_body = int(model.geom_bodyid[other_geom])
            if other_body not in right_hand_body_ids:
                continue
            body_name = mujoco.mj_id2name(
                model, mujoco.mjtObj.mjOBJ_BODY, other_body
            )
            contact_bodies.add(body_name)
            current_contact_bodies.add(body_name)
            contact_force = np.zeros(6)
            mujoco.mj_contactForce(
                model, data, contact_index, contact_force
            )
            max_normal_force = max(
                max_normal_force, abs(float(contact_force[0]))
            )
            normal_force = abs(float(contact_force[0]))
            contact_force_sum += normal_force
            contact_snapshot.append(
                {
                    "body": body_name,
                    "geom": mujoco.mj_id2name(
                        model, mujoco.mjtObj.mjOBJ_GEOM, other_geom
                    ),
                    "pos": np.round(contact.pos, 4).tolist(),
                    "normal": np.round(contact.frame[:3], 4).tolist(),
                    "normal_force": round(normal_force, 3),
                    "cube_is_geom1": geom1 == cube_geom_id,
                }
            )
        current_body_count = len(current_contact_bodies)
        if (
            current_body_count > max_contact_bodies
            or (
                current_body_count == max_contact_bodies
                and contact_force_sum > best_contact_force
            )
        ):
            best_contact_force = contact_force_sum
            best_contact_snapshot = contact_snapshot
        max_contacts = max(max_contacts, contact_count)
        max_contact_bodies = max(max_contact_bodies, current_body_count)
        if phase in ("lift", "hold") and contact_count > 0:
            lift_contact_steps += 1
        max_cube_z = max(max_cube_z, float(data.xpos[cube_body_id, 2]))

        if renderer is not None and step % args.render_every == 0:
            renderer.update_scene(data, camera="grasp_camera")
            Image.fromarray(renderer.render()).save(
                out_dir / f"frame_{frame_index:05d}.png"
            )
            frame_index += 1
        if viewer is not None:
            if not viewer.is_running():
                break
            viewer.sync()

    cube_final_pos = data.xpos[cube_body_id].copy()
    lifted_height = max_cube_z - cube_initial_pos[2]
    final_clearance = float(
        cube_final_pos[2] - TABLE_TOP_Z - cube_half_height
    )
    success = (
        max_contact_bodies >= 2
        and lifted_height >= 0.07
        and final_clearance >= 0.04
        and lift_contact_steps >= int(0.25 / model.opt.timestep)
    )
    if generated_motion and (
        fixed_arm_override_count != 0 or fixed_arm_pd_write_count != 0
    ):
        raise RuntimeError(
            "generated-motion mode used a fixed arm control path"
        )

    print(
        "[RESULT] "
        f"success={success} no_grip={args.no_grip} "
        f"max_contacts={max_contacts} "
        f"max_contact_bodies={max_contact_bodies} "
        f"contact_bodies={sorted(contact_bodies)} "
        f"max_normal_force={max_normal_force:.3f}N "
        f"lift_contact_time={lift_contact_steps * model.opt.timestep:.3f}s "
        f"lifted_height={lifted_height:.4f}m "
        f"final_clearance={final_clearance:.4f}m "
        f"final_cube_pos={np.round(cube_final_pos, 4).tolist()}"
    )
    print(
        "[CONTROL] "
        f"control_mode={control_mode} "
        f"fixed_arm_override_count={fixed_arm_override_count} "
        f"fixed_arm_pd_write_count={fixed_arm_pd_write_count} "
        f"reference_window_count={len(reference_window_hashes)} "
        f"reference_window_change_count={reference_window_change_count} "
        f"unique_reference_window_hashes={len(set(reference_window_hashes))} "
        f"reference_first_sha256="
        f"{reference_window_hashes[0] if reference_window_hashes else '-'} "
        f"reference_last_sha256="
        f"{reference_window_hashes[-1] if reference_window_hashes else '-'} "
        f"action_count={len(action_hashes)} "
        f"unique_action_hashes={len(set(action_hashes))} "
        f"action_first_sha256={action_hashes[0] if action_hashes else '-'} "
        f"action_last_sha256={action_hashes[-1] if action_hashes else '-'}"
    )
    if generated_motion:
        print(f"[REFERENCE] {encoder_adapter.window_log_line()}")
    print(f"[CONTACT_SNAPSHOT] {best_contact_snapshot}")
    print(
        "[FINGERTIP_DISTANCE] "
        + " ".join(
            f"{name}={distance:.5f}"
            for name, distance in min_fingertip_distance.items()
        )
    )
    print(
        "[FINGERTIP_POS] "
        + " ".join(
            f"{name}={np.round(data.geom_xpos[geom_id], 4).tolist()}"
            for name, geom_id in fingertip_geom_ids.items()
        )
    )
    wrist_position = data.xpos[wrist_body_id]
    wrist_rotation = data.xmat[wrist_body_id].reshape(3, 3)
    print(
        "[HAND_LOCAL] "
        f"cube={np.round(wrist_rotation.T @ (cube_final_pos - wrist_position), 4).tolist()} "
        + " ".join(
            f"{name}={np.round(wrist_rotation.T @ (data.geom_xpos[geom_id] - wrist_position), 4).tolist()}"
            for name, geom_id in fingertip_geom_ids.items()
        )
    )
    print(
        f"[HAND_Q] {np.round(data.qpos[hand_qpos_adr], 4).tolist()}"
    )
    pelvis_body_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_BODY, "pelvis"
    )
    print(
        "[ROBOT_STATE] "
        f"base_pos={np.round(data.qpos[:3], 4).tolist()} "
        f"up_z={data.xmat[pelvis_body_id].reshape(3, 3)[2, 2]:.4f}"
    )
    if args.export_baseline_csv:
        table_geom_id = mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_GEOM, "table_top"
        )
        hand_joint_names = []
        for actuator_id in RIGHT_HAND_ACTUATORS:
            joint_id = int(model.actuator_trnid[actuator_id, 0])
            hand_joint_names.append(
                mujoco.mj_id2name(
                    model, mujoco.mjtObj.mjOBJ_JOINT, joint_id
                )
            )
        manifest = write_physical_grasp_baseline(
            args.export_baseline_csv,
            args.export_baseline_manifest,
            frames=np.asarray(baseline_frames),
            source_fps=policy_hz,
            mujoco_joint_names=MUJOCO_G1_29_JOINT_NAMES,
            scene_path=args.scene,
            model_path=DEFAULT_G1_MODEL_XML,
            metrics={
                "success": bool(success),
                "max_contacts": int(max_contacts),
                "max_contact_bodies": int(max_contact_bodies),
                "contact_bodies": sorted(contact_bodies),
                "max_normal_force_newtons": float(max_normal_force),
                "lift_contact_time_seconds": float(
                    lift_contact_steps * model.opt.timestep
                ),
                "lifted_height_metres": float(lifted_height),
                "final_clearance_metres": float(final_clearance),
                "final_cube_position_xyz": cube_final_pos.tolist(),
            },
            hand_control={
                "representation": "independent PD; not stored in CSV",
                "joint_names": hand_joint_names,
                "open_target_radians": open_hand_target.tolist(),
                "closed_target_radians": closed_hand_target.tolist(),
                "close_start_seconds": float(args.close_start),
                "close_duration_seconds": float(args.close_duration),
                "thumb_delay_seconds": float(args.thumb_delay),
                "lift_start_seconds": float(args.lift_start),
                "lift_duration_seconds": float(args.lift_duration),
            },
            scene_objects={
                "robot": {
                    "name": "Unitree G1 29-DoF with hands",
                    "nq": int(model.nq),
                    "nv": int(model.nv),
                    "nu": int(model.nu),
                },
                "table": {
                    "geom": "table_top",
                    "centre_xyz": data.geom_xpos[table_geom_id].tolist(),
                    "half_size_xyz": model.geom_size[
                        table_geom_id
                    ].tolist(),
                },
                "cube": {
                    "body": "red_cube",
                    "geom": "red_cube_geom",
                    "initial_centre_xyz": cube_initial_pos.tolist(),
                    "half_size_xyz": model.geom_size[
                        cube_geom_id
                    ].tolist(),
                    "joint": "red_cube_free",
                },
            },
            reproduction_command=shlex.join([sys.executable, *sys.argv]),
        )
        print(
            "[BASELINE] "
            f"csv={Path(args.export_baseline_csv).resolve()} "
            f"manifest={Path(args.export_baseline_manifest).resolve()} "
            f"frames={manifest['csv']['shape'][0]} "
            f"sha256={manifest['csv']['sha256']}"
        )
    hand_contact_pairs = set()
    for contact_index in range(data.ncon):
        contact = data.contact[contact_index]
        geom_names = []
        hand_contact = False
        for geom_id in (int(contact.geom1), int(contact.geom2)):
            body_id = int(model.geom_bodyid[geom_id])
            body_name = mujoco.mj_id2name(
                model, mujoco.mjtObj.mjOBJ_BODY, body_id
            )
            hand_contact |= bool(
                body_name and body_name.startswith("right_hand_")
            )
            geom_names.append(
                mujoco.mj_id2name(
                    model, mujoco.mjtObj.mjOBJ_GEOM, geom_id
                )
                or f"geom_{geom_id}"
            )
        if hand_contact:
            hand_contact_pairs.add(tuple(geom_names))
    print(f"[HAND_CONTACTS] {sorted(hand_contact_pairs)}")
    if renderer is not None:
        renderer.close()
        print(f"[INFO] rendered_frames={frame_index} out_dir={out_dir.resolve()}")
    if viewer is not None:
        viewer.close()

    if args.no_grip and success:
        raise RuntimeError("negative control unexpectedly passed")
    if not args.no_grip and not success and not args.allow_failure:
        raise RuntimeError("physical grasp did not satisfy the success criteria")


if __name__ == "__main__":
    main()
