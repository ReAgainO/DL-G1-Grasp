import operator
from dataclasses import dataclass
from typing import Dict

import numpy as np

from motion_adapter.processing import (
    normalize_quaternion_sequence,
    quaternion_conjugate,
    quaternion_multiply,
    quaternion_to_matrix,
)
from motion_adapter.trajectory import MOTION_DOF, MotionTrajectory


SONIC_WINDOW_FRAMES = 10
SONIC_WINDOW_STEP = 5
SONIC_ANCHOR_DIM = 6
SONIC_REFERENCE_DIM = (
    SONIC_WINDOW_FRAMES * MOTION_DOF * 2
    + SONIC_WINDOW_FRAMES * SONIC_ANCHOR_DIM
)

JOINT_VELOCITY_KEY = "motion_joint_velocities_10frame_step5"
JOINT_POSITION_KEY = "motion_joint_positions_10frame_step5"
ANCHOR_ORIENTATION_KEY = "motion_anchor_orientation_10frame_step5"


def _readonly_array(value, dtype) -> np.ndarray:
    array = np.array(value, dtype=dtype, copy=True, order="C")
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class SonicReferenceWindow:
    requested_indices: np.ndarray
    frame_indices: np.ndarray
    joint_velocities: np.ndarray
    joint_positions: np.ndarray
    anchor_orientation_6d: np.ndarray

    def __post_init__(self) -> None:
        requested_indices = _readonly_array(
            self.requested_indices, np.int64
        )
        frame_indices = _readonly_array(self.frame_indices, np.int64)
        joint_velocities = _readonly_array(
            self.joint_velocities, np.float64
        )
        joint_positions = _readonly_array(
            self.joint_positions, np.float64
        )
        anchor_orientation = _readonly_array(
            self.anchor_orientation_6d, np.float64
        )

        expected_joint_shape = (SONIC_WINDOW_FRAMES, MOTION_DOF)
        expected_anchor_shape = (
            SONIC_WINDOW_FRAMES,
            SONIC_ANCHOR_DIM,
        )
        if requested_indices.shape != (SONIC_WINDOW_FRAMES,):
            raise ValueError(
                "requested_indices must have shape "
                f"({SONIC_WINDOW_FRAMES},)"
            )
        if frame_indices.shape != (SONIC_WINDOW_FRAMES,):
            raise ValueError(
                f"frame_indices must have shape ({SONIC_WINDOW_FRAMES},)"
            )
        if joint_velocities.shape != expected_joint_shape:
            raise ValueError(
                f"joint_velocities must have shape {expected_joint_shape}"
            )
        if joint_positions.shape != expected_joint_shape:
            raise ValueError(
                f"joint_positions must have shape {expected_joint_shape}"
            )
        if anchor_orientation.shape != expected_anchor_shape:
            raise ValueError(
                "anchor_orientation_6d must have shape "
                f"{expected_anchor_shape}"
            )
        for name, array in (
            ("joint_velocities", joint_velocities),
            ("joint_positions", joint_positions),
            ("anchor_orientation_6d", anchor_orientation),
        ):
            if not np.all(np.isfinite(array)):
                raise ValueError(f"{name} must contain only finite values")

        object.__setattr__(
            self, "requested_indices", requested_indices
        )
        object.__setattr__(self, "frame_indices", frame_indices)
        object.__setattr__(
            self, "joint_velocities", joint_velocities
        )
        object.__setattr__(self, "joint_positions", joint_positions)
        object.__setattr__(
            self, "anchor_orientation_6d", anchor_orientation
        )

    def as_encoder_obs(
        self, dtype=np.float32
    ) -> Dict[str, np.ndarray]:
        return {
            JOINT_VELOCITY_KEY: np.asarray(
                self.joint_velocities, dtype=dtype
            ).reshape(-1),
            JOINT_POSITION_KEY: np.asarray(
                self.joint_positions, dtype=dtype
            ).reshape(-1),
            ANCHOR_ORIENTATION_KEY: np.asarray(
                self.anchor_orientation_6d, dtype=dtype
            ).reshape(-1),
        }

    def flatten(self, dtype=np.float32) -> np.ndarray:
        encoder_obs = self.as_encoder_obs(dtype=dtype)
        result = np.concatenate(
            [
                encoder_obs[JOINT_VELOCITY_KEY],
                encoder_obs[JOINT_POSITION_KEY],
                encoder_obs[ANCHOR_ORIENTATION_KEY],
            ]
        )
        if result.shape != (SONIC_REFERENCE_DIM,):
            raise RuntimeError(
                "internal SONIC reference dimension mismatch: "
                f"expected {SONIC_REFERENCE_DIM}, got {result.shape}"
            )
        return result


def quaternion_to_anchor_6d(
    reference_quat_wxyz: np.ndarray,
    anchor_quat_wxyz: np.ndarray,
) -> np.ndarray:
    reference = np.asarray(reference_quat_wxyz, dtype=np.float64)
    if reference.ndim != 2 or reference.shape[1] != 4:
        raise ValueError(
            "reference_quat_wxyz must have shape (T, 4), "
            f"got {reference.shape}"
        )
    anchor = np.asarray(anchor_quat_wxyz, dtype=np.float64)
    if anchor.shape != (4,):
        raise ValueError(
            f"anchor_quat_wxyz must have shape (4,), got {anchor.shape}"
        )
    reference = normalize_quaternion_sequence(reference)
    anchor = normalize_quaternion_sequence(anchor.reshape(1, 4))[0]

    relative = quaternion_multiply(
        quaternion_conjugate(anchor),
        reference,
    )
    rotation_matrix = quaternion_to_matrix(relative)
    return rotation_matrix[..., :, :2].reshape(-1, SONIC_ANCHOR_DIM)


def build_sonic_reference_window(
    trajectory: MotionTrajectory,
    current_frame: int,
    *,
    anchor_quat_wxyz: np.ndarray,
) -> SonicReferenceWindow:
    if isinstance(current_frame, bool):
        raise ValueError("current_frame must be a non-negative integer")
    try:
        current_frame = operator.index(current_frame)
    except TypeError as exc:
        raise ValueError(
            "current_frame must be a non-negative integer"
        ) from exc
    if current_frame < 0:
        raise ValueError("current_frame must be a non-negative integer")

    offsets = np.arange(
        SONIC_WINDOW_FRAMES, dtype=np.int64
    ) * SONIC_WINDOW_STEP
    requested_indices = current_frame + offsets
    frame_indices = np.minimum(
        requested_indices, trajectory.frame_count - 1
    )
    reference_quaternions = trajectory.root_quat_wxyz[frame_indices]
    anchor_orientation = quaternion_to_anchor_6d(
        reference_quaternions,
        anchor_quat_wxyz,
    )

    return SonicReferenceWindow(
        requested_indices=requested_indices,
        frame_indices=frame_indices,
        joint_velocities=trajectory.joint_vel[frame_indices],
        joint_positions=trajectory.joint_pos[frame_indices],
        anchor_orientation_6d=anchor_orientation,
    )
