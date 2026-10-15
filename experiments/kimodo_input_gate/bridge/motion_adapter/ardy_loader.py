from pathlib import Path
from typing import Optional, Sequence, Union

from motion_adapter._csv_loader import load_qpos_csv
from motion_adapter.joint_contract import DEFAULT_JOINT_LIMIT_TOLERANCE
from motion_adapter.trajectory import MotionTrajectory


def load_ardy_csv(
    file_path: Union[str, Path],
    source_fps: float,
    *,
    source_joint_names: Optional[Sequence[str]] = None,
    model_xml_path: Optional[Union[str, Path]] = None,
    joint_limit_tolerance: float = DEFAULT_JOINT_LIMIT_TOLERANCE,
) -> MotionTrajectory:
    """Load a headerless ARDY G1 qpos CSV into canonical joint order."""

    return load_qpos_csv(
        file_path,
        source_fps,
        source="ardy",
        loader_name="ardy_loader",
        source_joint_names=source_joint_names,
        model_xml_path=model_xml_path,
        joint_limit_tolerance=joint_limit_tolerance,
    )
