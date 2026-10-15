from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence, Tuple

import numpy as np


MOTION_DOF = 29
QUATERNION_NORM_ATOL = 1e-4

# Canonical order consumed by the SONIC policy. Source-specific loaders must
# convert into this order before constructing a MotionTrajectory.
ISAACLAB_G1_29_JOINT_NAMES = (
    "left_hip_pitch_joint",
    "right_hip_pitch_joint",
    "waist_yaw_joint",
    "left_hip_roll_joint",
    "right_hip_roll_joint",
    "waist_roll_joint",
    "left_hip_yaw_joint",
    "right_hip_yaw_joint",
    "waist_pitch_joint",
    "left_knee_joint",
    "right_knee_joint",
    "left_shoulder_pitch_joint",
    "right_shoulder_pitch_joint",
    "left_ankle_pitch_joint",
    "right_ankle_pitch_joint",
    "left_shoulder_roll_joint",
    "right_shoulder_roll_joint",
    "left_ankle_roll_joint",
    "right_ankle_roll_joint",
    "left_shoulder_yaw_joint",
    "right_shoulder_yaw_joint",
    "left_elbow_joint",
    "right_elbow_joint",
    "left_wrist_roll_joint",
    "right_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "right_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_wrist_yaw_joint",
)


def _readonly_float_array(name: str, value: Any) -> np.ndarray:
    try:
        result = np.array(value, dtype=np.float64, copy=True, order="C")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a numeric array") from exc
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class MotionTrajectory:
    """Canonical G1 trajectory shared by motion-source adapters."""

    timestamps: np.ndarray
    root_pos: np.ndarray
    root_quat_wxyz: np.ndarray
    joint_pos: np.ndarray
    joint_vel: np.ndarray
    joint_names: Sequence[str] = ISAACLAB_G1_29_JOINT_NAMES
    source_fps: float = 0.0
    source: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        timestamps = _readonly_float_array("timestamps", self.timestamps)
        root_pos = _readonly_float_array("root_pos", self.root_pos)
        root_quat = _readonly_float_array(
            "root_quat_wxyz", self.root_quat_wxyz
        )
        joint_pos = _readonly_float_array("joint_pos", self.joint_pos)
        joint_vel = _readonly_float_array("joint_vel", self.joint_vel)

        if timestamps.ndim != 1:
            raise ValueError(
                f"timestamps must have shape (T,), got {timestamps.shape}"
            )
        frame_count = timestamps.shape[0]
        if frame_count == 0:
            raise ValueError("trajectory must contain at least one frame")

        expected_shapes = {
            "root_pos": (frame_count, 3),
            "root_quat_wxyz": (frame_count, 4),
            "joint_pos": (frame_count, MOTION_DOF),
            "joint_vel": (frame_count, MOTION_DOF),
        }
        arrays = {
            "root_pos": root_pos,
            "root_quat_wxyz": root_quat,
            "joint_pos": joint_pos,
            "joint_vel": joint_vel,
        }
        for name, expected_shape in expected_shapes.items():
            if arrays[name].shape != expected_shape:
                raise ValueError(
                    f"{name} must have shape {expected_shape}, "
                    f"got {arrays[name].shape}"
                )

        if frame_count > 1 and np.any(np.diff(timestamps) <= 0.0):
            raise ValueError("timestamps must be strictly increasing")

        quaternion_norms = np.linalg.norm(root_quat, axis=1)
        invalid_quaternion = np.flatnonzero(
            np.abs(quaternion_norms - 1.0) > QUATERNION_NORM_ATOL
        )
        if invalid_quaternion.size:
            frame = int(invalid_quaternion[0])
            raise ValueError(
                "root_quat_wxyz must contain unit quaternions; "
                f"frame {frame} has norm {quaternion_norms[frame]:.8f}"
            )

        names = self._validate_joint_names(self.joint_names)

        try:
            source_fps = float(self.source_fps)
        except (TypeError, ValueError) as exc:
            raise ValueError("source_fps must be a finite positive number") from exc
        if not np.isfinite(source_fps) or source_fps <= 0.0:
            raise ValueError("source_fps must be a finite positive number")

        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        source = self.source.strip()

        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        metadata = MappingProxyType(dict(self.metadata))

        object.__setattr__(self, "timestamps", timestamps)
        object.__setattr__(self, "root_pos", root_pos)
        object.__setattr__(self, "root_quat_wxyz", root_quat)
        object.__setattr__(self, "joint_pos", joint_pos)
        object.__setattr__(self, "joint_vel", joint_vel)
        object.__setattr__(self, "joint_names", names)
        object.__setattr__(self, "source_fps", source_fps)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "metadata", metadata)

    @staticmethod
    def _validate_joint_names(names: Sequence[str]) -> Tuple[str, ...]:
        if isinstance(names, (str, bytes)):
            raise ValueError("joint_names must be a sequence of 29 names")
        try:
            normalized = tuple(name.strip() for name in names)
        except (TypeError, AttributeError) as exc:
            raise ValueError("joint_names must contain only strings") from exc
        if len(normalized) != MOTION_DOF:
            raise ValueError(
                f"joint_names must contain {MOTION_DOF} names, "
                f"got {len(normalized)}"
            )
        if any(not name for name in normalized):
            raise ValueError("joint_names must not contain empty names")
        if len(set(normalized)) != MOTION_DOF:
            raise ValueError("joint_names must be unique")
        if normalized != ISAACLAB_G1_29_JOINT_NAMES:
            raise ValueError(
                "joint_names must use the canonical IsaacLab G1 29-DoF order"
            )
        return normalized

    @property
    def frame_count(self) -> int:
        return int(self.timestamps.shape[0])

    @property
    def duration(self) -> float:
        if self.frame_count == 1:
            return 0.0
        return float(self.timestamps[-1] - self.timestamps[0])
