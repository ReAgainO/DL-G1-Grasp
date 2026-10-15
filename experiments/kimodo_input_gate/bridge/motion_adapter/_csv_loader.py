import csv
import hashlib
import logging
from pathlib import Path
from typing import Optional, Sequence, Union

import numpy as np

from motion_adapter.joint_contract import (
    DEFAULT_JOINT_LIMIT_TOLERANCE,
    enforce_joint_limits,
    load_model_joint_contract,
    mujoco_to_isaac,
    validate_source_joint_names,
)
from motion_adapter.trajectory import (
    ISAACLAB_G1_29_JOINT_NAMES,
    MOTION_DOF,
    MotionTrajectory,
)


LOGGER = logging.getLogger(__name__)
QPOS_COLUMN_COUNT = 7 + MOTION_DOF


def _validate_source_fps(source_fps: float) -> float:
    try:
        fps = float(source_fps)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "source_fps must be a finite positive number"
        ) from exc
    if not np.isfinite(fps) or fps <= 0.0:
        raise ValueError("source_fps must be a finite positive number")
    return fps


def _read_qpos_csv(path: Path) -> np.ndarray:
    rows = []
    try:
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            for line_number, row in enumerate(csv.reader(csv_file), start=1):
                if len(row) != QPOS_COLUMN_COUNT:
                    raise ValueError(
                        f"{path}: line {line_number} must contain "
                        f"{QPOS_COLUMN_COUNT} columns, got {len(row)}"
                    )
                try:
                    values = [float(value) for value in row]
                except ValueError as exc:
                    raise ValueError(
                        f"{path}: line {line_number} contains non-numeric data"
                    ) from exc
                if not np.all(np.isfinite(values)):
                    raise ValueError(
                        f"{path}: line {line_number} contains NaN or Inf"
                    )
                rows.append(values)
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"failed to read motion CSV {path}: {exc}") from exc

    if not rows:
        raise ValueError(f"{path}: motion CSV is empty")
    return np.asarray(rows, dtype=np.float64)


def load_qpos_csv(
    file_path: Union[str, Path],
    source_fps: float,
    *,
    source: str,
    loader_name: str,
    source_joint_names: Optional[Sequence[str]] = None,
    model_xml_path: Optional[Union[str, Path]] = None,
    joint_limit_tolerance: float = DEFAULT_JOINT_LIMIT_TOLERANCE,
) -> MotionTrajectory:
    fps = _validate_source_fps(source_fps)
    source_names = validate_source_joint_names(source_joint_names)
    model_names, joint_limits, model_path, model_sha256 = (
        load_model_joint_contract(model_xml_path)
    )
    if source_names != model_names:
        raise ValueError(
            "source and model joint skeleton/order do not match"
        )

    path = Path(file_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"motion CSV does not exist: {path}")
    path = path.resolve()

    file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    qpos = _read_qpos_csv(path)
    frame_count = qpos.shape[0]
    timestamps = np.arange(frame_count, dtype=np.float64) / fps

    joint_pos_mujoco, clipping_records = enforce_joint_limits(
        qpos[:, 7:],
        joint_limits,
        tolerance=joint_limit_tolerance,
        source_path=path,
        logger=LOGGER,
    )
    joint_pos = mujoco_to_isaac(joint_pos_mujoco)
    if frame_count == 1:
        joint_vel = np.zeros_like(joint_pos)
    else:
        joint_vel = np.gradient(joint_pos, timestamps, axis=0)

    metadata = {
        "file_path": str(path),
        "file_sha256": file_sha256,
        "frame_count": frame_count,
        "source_fps": fps,
        "loader": loader_name,
        "source_joint_order": "mujoco_g1_29",
        "canonical_joint_order": "isaaclab_g1_29",
        "source_joint_names": source_names,
        "skeleton": "unitree_g1_29dof",
        "retargeting_required": False,
        "model_xml_path": str(model_path),
        "model_xml_sha256": model_sha256,
        "joint_limit_tolerance": float(joint_limit_tolerance),
        "joint_limit_clipping_count": len(clipping_records),
        "joint_limit_clipping": clipping_records,
    }
    trajectory = MotionTrajectory(
        timestamps=timestamps,
        root_pos=qpos[:, :3],
        root_quat_wxyz=qpos[:, 3:7],
        joint_pos=joint_pos,
        joint_vel=joint_vel,
        joint_names=ISAACLAB_G1_29_JOINT_NAMES,
        source_fps=fps,
        source=source,
        metadata=metadata,
    )
    LOGGER.info(
        "loaded motion source=%s loader=%s path=%s sha256=%s "
        "frames=%d fps=%.8g model_sha256=%s joint_limit_clips=%d",
        source,
        loader_name,
        path,
        file_sha256,
        frame_count,
        fps,
        model_sha256,
        len(clipping_records),
    )
    return trajectory
