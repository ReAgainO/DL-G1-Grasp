import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, Union

import numpy as np

from motion_adapter.trajectory import MOTION_DOF


BASELINE_COLUMN_COUNT = 7 + MOTION_DOF


def file_sha256(path: Union[str, Path]) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_baseline_frames(frames: np.ndarray) -> np.ndarray:
    values = np.asarray(frames, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != BASELINE_COLUMN_COUNT:
        raise ValueError(
            "baseline frames must have shape "
            f"(T, {BASELINE_COLUMN_COUNT}), got {values.shape}"
        )
    if values.shape[0] == 0:
        raise ValueError("baseline frames must not be empty")
    if not np.all(np.isfinite(values)):
        raise ValueError("baseline frames must contain only finite values")
    quaternion_norms = np.linalg.norm(values[:, 3:7], axis=1)
    if np.max(np.abs(quaternion_norms - 1.0)) > 1e-4:
        raise ValueError("baseline root quaternions must be unit length")
    return values


def write_physical_grasp_baseline(
    csv_path: Union[str, Path],
    manifest_path: Union[str, Path],
    *,
    frames: np.ndarray,
    source_fps: float,
    mujoco_joint_names: Sequence[str],
    scene_path: Union[str, Path],
    model_path: Union[str, Path],
    metrics: Mapping[str, Any],
    hand_control: Mapping[str, Any],
    scene_objects: Mapping[str, Any],
    reproduction_command: str,
) -> Mapping[str, Any]:
    values = validate_baseline_frames(frames)
    fps = float(source_fps)
    if not np.isfinite(fps) or fps <= 0.0:
        raise ValueError("source_fps must be a finite positive number")
    names = tuple(mujoco_joint_names)
    if len(names) != MOTION_DOF or len(set(names)) != MOTION_DOF:
        raise ValueError("mujoco_joint_names must contain 29 unique names")
    if metrics.get("success") is not True:
        raise ValueError("only a successful physical grasp may be exported")

    csv_path = Path(csv_path).expanduser().resolve()
    manifest_path = Path(manifest_path).expanduser().resolve()
    if csv_path == manifest_path:
        raise ValueError("CSV and manifest paths must be different")
    scene_path = Path(scene_path).expanduser().resolve()
    model_path = Path(model_path).expanduser().resolve()
    for label, path in (("scene", scene_path), ("model", model_path)):
        if not path.is_file():
            raise FileNotFoundError(f"{label} file does not exist: {path}")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(csv_path, values, delimiter=",", fmt="%.10g")

    manifest = {
        "schema_version": 1,
        "artifact_type": "scene-conditioned-physical-grasp-keyframe-baseline",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "csv": {
            "path": str(csv_path),
            "sha256": file_sha256(csv_path),
            "shape": [int(values.shape[0]), BASELINE_COLUMN_COUNT],
            "source_fps": fps,
            "duration_seconds": float(values.shape[0] / fps),
            "header": False,
            "columns": {
                "0:3": "root position xyz, world frame, metres",
                "3:7": "root quaternion wxyz",
                "7:36": "29 body joints, MuJoCo actuator order, radians",
            },
            "joint_names": list(names),
        },
        "coordinate_contract": {
            "handedness": "right-handed",
            "world_up": "+Z",
            "quaternion_order": "wxyz",
            "position_unit": "metre",
            "joint_unit": "radian",
        },
        "scene": {
            "path": str(scene_path),
            "sha256": file_sha256(scene_path),
            "model_path": str(model_path),
            "model_sha256": file_sha256(model_path),
            "objects": dict(scene_objects),
        },
        "hand_control": dict(hand_control),
        "acceptance_metrics": dict(metrics),
        "provenance": {
            "producer": "runners/run_grasp.py keyframe mode",
            "reproduction_command": reproduction_command,
            "scene_conditioned": True,
            "physical_contact_only": True,
            "uses_weld_or_adhesion": False,
        },
        "scope": {
            "csv_contains_hand_joints": False,
            "csv_contains_body_and_root_ground_truth": True,
            "sonic_closed_loop_replay_validated": False,
            "note": (
                "This is recorded keyframe-controller ground truth for the "
                "pinned scene. It is not a claim that SONIC replay of the CSV "
                "reproduces the grasp."
            ),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
