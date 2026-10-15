from typing import Optional, Sequence

import numpy as np

from motion_adapter.trajectory import MotionTrajectory


_TIME_ATOL = 1e-10
_QUATERNION_EPS = 1e-12
_SLERP_LINEAR_THRESHOLD = 0.9995


def normalize_quaternion_sequence(quaternions_wxyz: np.ndarray) -> np.ndarray:
    quaternions = np.asarray(quaternions_wxyz, dtype=np.float64)
    if quaternions.ndim != 2 or quaternions.shape[1] != 4:
        raise ValueError(
            "quaternions_wxyz must have shape (T, 4), "
            f"got {quaternions.shape}"
        )
    if quaternions.shape[0] == 0:
        raise ValueError("quaternions_wxyz must not be empty")
    if not np.all(np.isfinite(quaternions)):
        raise ValueError("quaternions_wxyz must contain only finite values")

    norms = np.linalg.norm(quaternions, axis=1)
    invalid = np.flatnonzero(norms <= _QUATERNION_EPS)
    if invalid.size:
        raise ValueError(
            "quaternions_wxyz must not contain zero quaternions; "
            f"frame {int(invalid[0])} has norm {norms[invalid[0]]:.9g}"
        )

    normalized = quaternions / norms[:, None]
    for frame in range(1, normalized.shape[0]):
        if np.dot(normalized[frame - 1], normalized[frame]) < 0.0:
            normalized[frame] *= -1.0
    return normalized


def quaternion_yaw(quaternion_wxyz: Sequence[float]) -> float:
    quaternion = normalize_quaternion_sequence(
        np.asarray(quaternion_wxyz, dtype=np.float64).reshape(1, 4)
    )[0]
    w, x, y, z = quaternion
    return float(
        np.arctan2(
            2.0 * (w * z + x * y),
            1.0 - 2.0 * (y * y + z * z),
        )
    )


def _yaw_quaternion(angle: float) -> np.ndarray:
    half_angle = 0.5 * angle
    return np.array(
        [np.cos(half_angle), 0.0, 0.0, np.sin(half_angle)],
        dtype=np.float64,
    )


def quaternion_multiply(
    left_wxyz: np.ndarray, right_wxyz: np.ndarray
) -> np.ndarray:
    left = np.asarray(left_wxyz, dtype=np.float64)
    right = np.asarray(right_wxyz, dtype=np.float64)
    lw, lx, ly, lz = np.moveaxis(left, -1, 0)
    rw, rx, ry, rz = np.moveaxis(right, -1, 0)
    return np.stack(
        (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ),
        axis=-1,
    )


def quaternion_conjugate(quaternion_wxyz: np.ndarray) -> np.ndarray:
    quaternion = np.asarray(quaternion_wxyz, dtype=np.float64)
    if quaternion.shape[-1:] != (4,):
        raise ValueError(
            "quaternion_wxyz must end in dimension 4, "
            f"got {quaternion.shape}"
        )
    result = quaternion.copy()
    result[..., 1:] *= -1.0
    return result


def quaternion_to_matrix(quaternion_wxyz: np.ndarray) -> np.ndarray:
    quaternion = np.asarray(quaternion_wxyz, dtype=np.float64)
    if quaternion.shape[-1:] != (4,):
        raise ValueError(
            "quaternion_wxyz must end in dimension 4, "
            f"got {quaternion.shape}"
        )
    original_shape = quaternion.shape[:-1]
    normalized = normalize_quaternion_sequence(
        quaternion.reshape(-1, 4)
    ).reshape(original_shape + (4,))
    w, x, y, z = np.moveaxis(normalized, -1, 0)
    return np.stack(
        (
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y - w * z),
            2.0 * (x * z + w * y),
            2.0 * (x * y + w * z),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z - w * x),
            2.0 * (x * z - w * y),
            2.0 * (y * z + w * x),
            1.0 - 2.0 * (x * x + y * y),
        ),
        axis=-1,
    ).reshape(original_shape + (3, 3))


def _validate_target_root_pos(target_root_pos: Sequence[float]) -> np.ndarray:
    try:
        target = np.asarray(target_root_pos, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("target_root_pos must contain three numbers") from exc
    if target.shape != (3,) or not np.all(np.isfinite(target)):
        raise ValueError(
            "target_root_pos must be a finite vector with shape (3,)"
        )
    return target


def register_root_frame(
    trajectory: MotionTrajectory,
    target_root_pos: Sequence[float],
    target_heading: float = 0.0,
) -> MotionTrajectory:
    """Register the source root pose to a robot pose in the target scene."""

    target_position = _validate_target_root_pos(target_root_pos)
    try:
        target_heading = float(target_heading)
    except (TypeError, ValueError) as exc:
        raise ValueError("target_heading must be a finite number") from exc
    if not np.isfinite(target_heading):
        raise ValueError("target_heading must be a finite number")

    source_quaternions = normalize_quaternion_sequence(
        trajectory.root_quat_wxyz
    )
    source_heading = quaternion_yaw(source_quaternions[0])
    heading_delta = target_heading - source_heading

    cos_yaw = np.cos(heading_delta)
    sin_yaw = np.sin(heading_delta)
    rotation_z = np.array(
        [
            [cos_yaw, -sin_yaw, 0.0],
            [sin_yaw, cos_yaw, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    root_offsets = trajectory.root_pos - trajectory.root_pos[0]
    registered_pos = target_position + root_offsets @ rotation_z.T
    registered_quat = quaternion_multiply(
        _yaw_quaternion(heading_delta),
        source_quaternions,
    )
    registered_quat = normalize_quaternion_sequence(registered_quat)

    metadata = dict(trajectory.metadata)
    metadata["root_registration"] = {
        "source_root_pos": tuple(float(x) for x in trajectory.root_pos[0]),
        "source_heading": source_heading,
        "target_root_pos": tuple(float(x) for x in target_position),
        "target_heading": target_heading,
        "heading_delta": heading_delta,
    }
    metadata["initial_heading_normalized"] = bool(
        np.isclose(target_heading, 0.0, atol=1e-12)
    )
    return MotionTrajectory(
        timestamps=trajectory.timestamps,
        root_pos=registered_pos,
        root_quat_wxyz=registered_quat,
        joint_pos=trajectory.joint_pos,
        joint_vel=trajectory.joint_vel,
        joint_names=trajectory.joint_names,
        source_fps=trajectory.source_fps,
        source=trajectory.source,
        metadata=metadata,
    )


def _validate_target_timestamps(
    target_timestamps: np.ndarray,
    source_timestamps: np.ndarray,
) -> np.ndarray:
    try:
        target = np.asarray(target_timestamps, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("target_timestamps must be a numeric array") from exc
    if target.ndim != 1 or target.shape[0] == 0:
        raise ValueError("target_timestamps must have shape (T,) with T > 0")
    if not np.all(np.isfinite(target)):
        raise ValueError("target_timestamps must contain only finite values")
    if target.shape[0] > 1 and np.any(np.diff(target) <= 0.0):
        raise ValueError("target_timestamps must be strictly increasing")

    source_start = float(source_timestamps[0])
    source_end = float(source_timestamps[-1])
    if target[0] < source_start - _TIME_ATOL:
        raise ValueError("target_timestamps start before the source trajectory")
    if target[-1] > source_end + _TIME_ATOL:
        raise ValueError("target_timestamps end after the source trajectory")

    target = target.copy()
    if np.isclose(target[0], source_start, atol=_TIME_ATOL, rtol=0.0):
        target[0] = source_start
    if np.isclose(target[-1], source_end, atol=_TIME_ATOL, rtol=0.0):
        target[-1] = source_end
    return target


def _interpolate_columns(
    source_timestamps: np.ndarray,
    values: np.ndarray,
    target_timestamps: np.ndarray,
) -> np.ndarray:
    return np.column_stack(
        [
            np.interp(target_timestamps, source_timestamps, values[:, index])
            for index in range(values.shape[1])
        ]
    )


def _slerp_wxyz(
    source_timestamps: np.ndarray,
    quaternions_wxyz: np.ndarray,
    target_timestamps: np.ndarray,
) -> np.ndarray:
    source_quaternions = normalize_quaternion_sequence(quaternions_wxyz)
    if source_quaternions.shape[0] == 1:
        return np.repeat(
            source_quaternions,
            target_timestamps.shape[0],
            axis=0,
        )

    right_indices = np.searchsorted(
        source_timestamps, target_timestamps, side="right"
    )
    left_indices = np.clip(
        right_indices - 1, 0, source_timestamps.shape[0] - 2
    )
    right_indices = left_indices + 1
    left_times = source_timestamps[left_indices]
    right_times = source_timestamps[right_indices]
    fraction = (
        (target_timestamps - left_times) / (right_times - left_times)
    )

    left = source_quaternions[left_indices]
    right = source_quaternions[right_indices]
    dot = np.sum(left * right, axis=1)
    negative = dot < 0.0
    right[negative] *= -1.0
    dot = np.abs(dot)
    dot = np.clip(dot, -1.0, 1.0)

    result = np.empty_like(left)
    linear = dot > _SLERP_LINEAR_THRESHOLD
    if np.any(linear):
        linear_fraction = fraction[linear, None]
        result[linear] = (
            (1.0 - linear_fraction) * left[linear]
            + linear_fraction * right[linear]
        )
    spherical = ~linear
    if np.any(spherical):
        theta = np.arccos(dot[spherical])
        sin_theta = np.sin(theta)
        spherical_fraction = fraction[spherical]
        left_weight = np.sin((1.0 - spherical_fraction) * theta) / sin_theta
        right_weight = np.sin(spherical_fraction * theta) / sin_theta
        result[spherical] = (
            left_weight[:, None] * left[spherical]
            + right_weight[:, None] * right[spherical]
        )
    return normalize_quaternion_sequence(result)


def resample_trajectory_at(
    trajectory: MotionTrajectory,
    target_timestamps: np.ndarray,
    *,
    target_fps: Optional[float] = None,
) -> MotionTrajectory:
    target_timestamps = _validate_target_timestamps(
        target_timestamps, trajectory.timestamps
    )
    if target_fps is not None:
        try:
            target_fps = float(target_fps)
        except (TypeError, ValueError) as exc:
            raise ValueError("target_fps must be a finite positive number") from exc
        if not np.isfinite(target_fps) or target_fps <= 0.0:
            raise ValueError("target_fps must be a finite positive number")

    if trajectory.frame_count == 1:
        root_pos = np.repeat(
            trajectory.root_pos, target_timestamps.shape[0], axis=0
        )
        joint_pos = np.repeat(
            trajectory.joint_pos, target_timestamps.shape[0], axis=0
        )
    else:
        root_pos = _interpolate_columns(
            trajectory.timestamps,
            trajectory.root_pos,
            target_timestamps,
        )
        joint_pos = _interpolate_columns(
            trajectory.timestamps,
            trajectory.joint_pos,
            target_timestamps,
        )
    root_quat = _slerp_wxyz(
        trajectory.timestamps,
        trajectory.root_quat_wxyz,
        target_timestamps,
    )

    if target_timestamps.shape[0] == 1:
        joint_vel = np.zeros_like(joint_pos)
    else:
        joint_vel = np.gradient(
            joint_pos, target_timestamps, axis=0, edge_order=1
        )

    metadata = dict(trajectory.metadata)
    metadata["resampling"] = {
        "source_frame_count": trajectory.frame_count,
        "target_frame_count": int(target_timestamps.shape[0]),
        "source_start_time": float(trajectory.timestamps[0]),
        "source_end_time": float(trajectory.timestamps[-1]),
        "target_start_time": float(target_timestamps[0]),
        "target_end_time": float(target_timestamps[-1]),
        "target_fps": target_fps,
        "method": "linear_position_joint+slerp_wxyz",
        "joint_velocity_recomputed": True,
    }
    metadata["quaternion_normalized"] = True
    metadata["quaternion_sign_continuous"] = True
    return MotionTrajectory(
        timestamps=target_timestamps,
        root_pos=root_pos,
        root_quat_wxyz=root_quat,
        joint_pos=joint_pos,
        joint_vel=joint_vel,
        joint_names=trajectory.joint_names,
        source_fps=trajectory.source_fps,
        source=trajectory.source,
        metadata=metadata,
    )


def _uniform_target_timestamps(
    start_time: float, end_time: float, target_fps: float
) -> np.ndarray:
    if end_time == start_time:
        return np.array([start_time], dtype=np.float64)
    step = 1.0 / target_fps
    full_steps = int(np.floor((end_time - start_time) / step + _TIME_ATOL))
    timestamps = start_time + np.arange(full_steps + 1) * step
    if end_time - timestamps[-1] > _TIME_ATOL:
        timestamps = np.append(timestamps, end_time)
    else:
        timestamps[-1] = end_time
    return timestamps


def resample_trajectory(
    trajectory: MotionTrajectory, target_fps: float
) -> MotionTrajectory:
    try:
        target_fps = float(target_fps)
    except (TypeError, ValueError) as exc:
        raise ValueError("target_fps must be a finite positive number") from exc
    if not np.isfinite(target_fps) or target_fps <= 0.0:
        raise ValueError("target_fps must be a finite positive number")

    target_timestamps = _uniform_target_timestamps(
        float(trajectory.timestamps[0]),
        float(trajectory.timestamps[-1]),
        target_fps,
    )
    return resample_trajectory_at(
        trajectory,
        target_timestamps,
        target_fps=target_fps,
    )


def prepare_trajectory(
    trajectory: MotionTrajectory,
    *,
    target_fps: float,
    target_root_pos: Sequence[float],
    target_heading: float = 0.0,
) -> MotionTrajectory:
    registered = register_root_frame(
        trajectory,
        target_root_pos=target_root_pos,
        target_heading=target_heading,
    )
    return resample_trajectory(registered, target_fps=target_fps)
