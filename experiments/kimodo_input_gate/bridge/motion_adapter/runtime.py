from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from motion_adapter.ardy_loader import load_ardy_csv
from motion_adapter.kimodo_loader import load_kimodo_csv
from motion_adapter.processing import prepare_trajectory
from motion_adapter.trajectory import MotionTrajectory


MOTION_LOADERS = {
    "kimodo": load_kimodo_csv,
    "ardy": load_ardy_csv,
}


@dataclass(frozen=True)
class MotionRuntime:
    trajectory: MotionTrajectory
    motion_start: float
    motion_speed: float

    def startup_log_line(self) -> str:
        metadata = self.trajectory.metadata
        resampling = metadata.get("resampling", {})
        return (
            f"motion_source={self.trajectory.source} "
            f"loader={metadata['loader']} "
            f"motion_file={metadata['file_path']} "
            f"sha256={metadata['file_sha256']} "
            f"source_frames={metadata['frame_count']} "
            f"source_fps={metadata['source_fps']:.8g} "
            f"prepared_frames={self.trajectory.frame_count} "
            f"target_fps={resampling.get('target_fps')} "
            f"motion_start={self.motion_start:.8g} "
            f"motion_speed={self.motion_speed:.8g}"
        )


def add_motion_arguments(parser) -> None:
    parser.add_argument(
        "--motion-source",
        choices=tuple(MOTION_LOADERS),
        default=None,
    )
    parser.add_argument("--motion-file", type=str, default=None)
    parser.add_argument("--source-fps", type=float, default=None)
    parser.add_argument(
        "--motion-start",
        type=float,
        default=0.0,
        help="source trajectory start offset in seconds",
    )
    parser.add_argument(
        "--motion-speed",
        type=float,
        default=1.0,
        help="trajectory playback speed multiplier",
    )


def _finite_number(name: str, value, *, positive: bool) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    valid = np.isfinite(result) and (result > 0.0 if positive else result >= 0.0)
    if not valid:
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{name} must be a finite {qualifier} number")
    return result


def load_motion_runtime(
    args,
    *,
    target_fps: float,
    target_root_pos: Sequence[float],
    target_heading: float,
) -> Optional[MotionRuntime]:
    source = getattr(args, "motion_source", None)
    file_path = getattr(args, "motion_file", None)
    source_fps = getattr(args, "source_fps", None)
    motion_start = _finite_number(
        "motion_start", getattr(args, "motion_start", 0.0), positive=False
    )
    motion_speed = _finite_number(
        "motion_speed", getattr(args, "motion_speed", 1.0), positive=True
    )

    supplied = (source is not None, file_path is not None, source_fps is not None)
    if any(supplied) and not all(supplied):
        raise ValueError(
            "--motion-source, --motion-file, and --source-fps must be "
            "provided together"
        )
    if not any(supplied):
        if motion_start != 0.0 or motion_speed != 1.0:
            raise ValueError(
                "--motion-start and --motion-speed require a motion source"
            )
        return None
    if source not in MOTION_LOADERS:
        raise ValueError(
            f"motion_source must be one of {tuple(MOTION_LOADERS)}, got {source!r}"
        )
    source_fps = _finite_number("source_fps", source_fps, positive=True)
    path = Path(file_path).expanduser()
    loader = MOTION_LOADERS[source]
    loaded = loader(path, source_fps=source_fps)
    prepared = prepare_trajectory(
        loaded,
        target_fps=_finite_number("target_fps", target_fps, positive=True),
        target_root_pos=target_root_pos,
        target_heading=target_heading,
    )
    return MotionRuntime(
        trajectory=prepared,
        motion_start=motion_start,
        motion_speed=motion_speed,
    )
