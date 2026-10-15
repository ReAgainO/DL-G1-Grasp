import hashlib
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

import numpy as np

from adapters.sonic_action_adapter import I2M, M2I
from motion_adapter.trajectory import (
    ISAACLAB_G1_29_JOINT_NAMES,
    MOTION_DOF,
)


DEFAULT_G1_MODEL_XML = (
    Path(__file__).resolve().parents[1] / "g1/g1_29dof_with_hand.xml"
)
DEFAULT_JOINT_LIMIT_TOLERANCE = 0.02

# Derived from the canonical names through the existing mapping. Do not define
# a second index mapping in the motion adapter.
MUJOCO_G1_29_JOINT_NAMES = tuple(
    ISAACLAB_G1_29_JOINT_NAMES[M2I[mujoco_index]]
    for mujoco_index in range(MOTION_DOF)
)


def mujoco_to_isaac(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values)
    if array.shape[-1:] != (MOTION_DOF,):
        raise ValueError(
            f"MuJoCo joint array must end in {MOTION_DOF}, got {array.shape}"
        )
    return array[..., I2M]


def isaac_to_mujoco(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values)
    if array.shape[-1:] != (MOTION_DOF,):
        raise ValueError(
            f"IsaacLab joint array must end in {MOTION_DOF}, got {array.shape}"
        )
    return array[..., M2I]


def validate_source_joint_names(
    joint_names: Optional[Sequence[str]],
) -> Tuple[str, ...]:
    if joint_names is None:
        return MUJOCO_G1_29_JOINT_NAMES
    if isinstance(joint_names, (str, bytes)):
        raise ValueError("source_joint_names must be a sequence of 29 names")
    try:
        names = tuple(name.strip() for name in joint_names)
    except (TypeError, AttributeError) as exc:
        raise ValueError(
            "source_joint_names must contain only strings"
        ) from exc
    if names != MUJOCO_G1_29_JOINT_NAMES:
        raise ValueError(
            "source joint skeleton/order does not match the expected "
            "MuJoCo G1 29-DoF contract"
        )
    return names


def load_model_joint_contract(
    model_xml_path: Optional[Union[str, Path]] = None,
) -> Tuple[Tuple[str, ...], np.ndarray, Path, str]:
    path = (
        DEFAULT_G1_MODEL_XML
        if model_xml_path is None
        else Path(model_xml_path).expanduser()
    )
    if not path.is_file():
        raise FileNotFoundError(f"G1 model XML does not exist: {path}")
    path = path.resolve()
    model_bytes = path.read_bytes()
    model_sha256 = hashlib.sha256(model_bytes).hexdigest()

    try:
        root = ET.fromstring(model_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"failed to parse G1 model XML {path}: {exc}") from exc

    actuator = root.find("actuator")
    if actuator is None:
        raise ValueError(f"{path}: model has no actuator section")
    motors = actuator.findall("motor")
    if len(motors) < MOTION_DOF:
        raise ValueError(
            f"{path}: model must have at least {MOTION_DOF} motors, "
            f"got {len(motors)}"
        )

    joint_elements = {
        joint.get("name"): joint
        for joint in root.findall(".//joint")
        if joint.get("name")
    }
    names = tuple(motor.get("joint", "") for motor in motors[:MOTION_DOF])
    if names != MUJOCO_G1_29_JOINT_NAMES:
        raise ValueError(
            f"{path}: first 29 actuator joints do not match the expected "
            "MuJoCo G1 29-DoF skeleton/order"
        )

    limits = np.empty((MOTION_DOF, 2), dtype=np.float64)
    for index, name in enumerate(names):
        joint = joint_elements.get(name)
        if joint is None:
            raise ValueError(f"{path}: actuator joint {name!r} is undefined")
        joint_type = joint.get("type", "hinge")
        if joint_type != "hinge":
            raise ValueError(
                f"{path}: joint {name!r} must be hinge, got {joint_type!r}"
            )
        range_text = joint.get("range")
        if range_text is None:
            raise ValueError(f"{path}: joint {name!r} has no range")
        try:
            joint_range = np.asarray(
                [float(value) for value in range_text.split()],
                dtype=np.float64,
            )
        except ValueError as exc:
            raise ValueError(
                f"{path}: joint {name!r} has a non-numeric range"
            ) from exc
        if (
            joint_range.shape != (2,)
            or not np.all(np.isfinite(joint_range))
            or joint_range[0] >= joint_range[1]
        ):
            raise ValueError(
                f"{path}: joint {name!r} has invalid range {range_text!r}"
            )
        limits[index] = joint_range

    limits.setflags(write=False)
    return names, limits, path, model_sha256


def enforce_joint_limits(
    joint_pos_mujoco: np.ndarray,
    joint_limits_mujoco: np.ndarray,
    *,
    tolerance: float,
    source_path: Path,
    logger: logging.Logger,
) -> Tuple[np.ndarray, Tuple[dict, ...]]:
    try:
        tolerance = float(tolerance)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "joint_limit_tolerance must be a finite non-negative number"
        ) from exc
    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError(
            "joint_limit_tolerance must be a finite non-negative number"
        )

    values = np.asarray(joint_pos_mujoco, dtype=np.float64)
    limits = np.asarray(joint_limits_mujoco, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != MOTION_DOF:
        raise ValueError(
            f"joint_pos_mujoco must have shape (T, {MOTION_DOF}), "
            f"got {values.shape}"
        )
    if limits.shape != (MOTION_DOF, 2):
        raise ValueError(
            f"joint_limits_mujoco must have shape ({MOTION_DOF}, 2), "
            f"got {limits.shape}"
        )

    lower_excess = np.maximum(limits[None, :, 0] - values, 0.0)
    upper_excess = np.maximum(values - limits[None, :, 1], 0.0)
    excess = np.maximum(lower_excess, upper_excess)
    violations = np.argwhere(excess > 0.0)
    if violations.size == 0:
        return values.copy(), ()

    worst_frame, worst_joint = np.unravel_index(
        int(np.argmax(excess)), excess.shape
    )
    worst_excess = float(excess[worst_frame, worst_joint])
    if worst_excess > tolerance:
        joint_name = MUJOCO_G1_29_JOINT_NAMES[worst_joint]
        value = float(values[worst_frame, worst_joint])
        lower, upper = limits[worst_joint]
        raise ValueError(
            f"{source_path}: joint limit exceeded beyond tolerance; "
            f"frame={worst_frame} joint={joint_name} value={value:.9g} "
            f"range=[{lower:.9g}, {upper:.9g}] "
            f"excess={worst_excess:.9g} tolerance={tolerance:.9g}"
        )

    clipped = np.clip(values, limits[:, 0], limits[:, 1])
    records = []
    for frame, joint_index in violations:
        frame = int(frame)
        joint_index = int(joint_index)
        lower, upper = limits[joint_index]
        record = {
            "frame": frame,
            "joint": MUJOCO_G1_29_JOINT_NAMES[joint_index],
            "value": float(values[frame, joint_index]),
            "lower": float(lower),
            "upper": float(upper),
            "excess": float(excess[frame, joint_index]),
        }
        records.append(record)
        logger.warning(
            "clipped joint limit path=%s frame=%d joint=%s value=%.9g "
            "range=[%.9g, %.9g] excess=%.9g tolerance=%.9g",
            source_path,
            frame,
            record["joint"],
            record["value"],
            record["lower"],
            record["upper"],
            record["excess"],
            tolerance,
        )
    return clipped, tuple(records)
