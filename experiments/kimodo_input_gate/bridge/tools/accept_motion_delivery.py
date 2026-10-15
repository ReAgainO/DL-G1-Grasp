#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from motion_adapter import (  # noqa: E402
    file_sha256,
    load_ardy_csv,
    load_kimodo_csv,
    validate_baseline_frames,
)


ASSET_DIR = REPO_ROOT / "server_reports/assets/kimodo_ardy_qpos"
BASELINE_DIR = REPO_ROOT / "baselines/g1_cube_grasp_v1"
SCENE_PATH = REPO_ROOT / "g1/scene_grasp_hand.xml"
MODEL_PATH = REPO_ROOT / "g1/g1_29dof_with_hand.xml"
RESULT_PATTERN = re.compile(r"\[RESULT\] success=(True|False)")
CONTROL_PATTERN = re.compile(
    r"\[CONTROL\].*control_mode=(\S+).*"
    r"fixed_arm_override_count=(\d+).*"
    r"fixed_arm_pd_write_count=(\d+).*"
    r"reference_window_count=(\d+).*"
    r"reference_window_change_count=(\d+)"
)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def validate_scene():
    model = mujoco.MjModel.from_xml_path(str(SCENE_PATH))
    check((model.nq, model.nv, model.nu) == (57, 55, 43), "model dimensions")
    for object_type, name in (
        (mujoco.mjtObj.mjOBJ_BODY, "pelvis"),
        (mujoco.mjtObj.mjOBJ_BODY, "grasp_table"),
        (mujoco.mjtObj.mjOBJ_BODY, "red_cube"),
        (mujoco.mjtObj.mjOBJ_GEOM, "table_top"),
        (mujoco.mjtObj.mjOBJ_GEOM, "red_cube_geom"),
        (mujoco.mjtObj.mjOBJ_JOINT, "red_cube_free"),
    ):
        check(
            mujoco.mj_name2id(model, object_type, name) >= 0,
            f"scene object missing: {name}",
        )
    cube_joint = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_JOINT, "red_cube_free"
    )
    check(
        model.jnt_type[cube_joint] == mujoco.mjtJoint.mjJNT_FREE,
        "cube joint is not free",
    )
    check(model.neq == 0, "scene must not contain equality constraints")
    xml_text = (
        SCENE_PATH.read_text(encoding="utf-8")
        + MODEL_PATH.read_text(encoding="utf-8")
    ).lower()
    check("<weld" not in xml_text, "scene contains weld")
    check("adhesion" not in xml_text, "scene contains adhesion")
    return {"nq": model.nq, "nv": model.nv, "nu": model.nu, "neq": model.neq}


def validate_loaders():
    cases = (
        ("kimodo_walk_s0.csv", load_kimodo_csv, 120, "kimodo"),
        ("test_pickup.csv", load_kimodo_csv, None, "kimodo"),
        ("ardy_final_s0.csv", load_ardy_csv, 100, "ardy"),
        ("ardy_r5_sha4f_early.csv", load_ardy_csv, 200, "ardy"),
    )
    result = {}
    for name, loader, expected_frames, source in cases:
        path = ASSET_DIR / name
        trajectory = loader(path, source_fps=50.0)
        if expected_frames is not None:
            check(
                trajectory.frame_count == expected_frames,
                f"{name}: unexpected frame count",
            )
        check(trajectory.source == source, f"{name}: wrong source")
        result[name] = {
            "frames": trajectory.frame_count,
            "sha256": trajectory.metadata["file_sha256"],
            "loader": trajectory.metadata["loader"],
        }
    return result


def validate_baseline():
    csv_path = BASELINE_DIR / "g1_cube_grasp_keyframe_50hz.csv"
    manifest_path = BASELINE_DIR / "g1_cube_grasp_keyframe_50hz.manifest.json"
    check(csv_path.is_file(), f"baseline CSV missing: {csv_path}")
    check(manifest_path.is_file(), f"baseline manifest missing: {manifest_path}")
    frames = np.loadtxt(csv_path, delimiter=",")
    validate_baseline_frames(frames)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    check(manifest["csv"]["shape"] == list(frames.shape), "baseline shape mismatch")
    check(
        manifest["csv"]["sha256"] == file_sha256(csv_path),
        "baseline CSV hash mismatch",
    )
    check(
        manifest["scene"]["sha256"] == file_sha256(SCENE_PATH),
        "baseline scene hash mismatch",
    )
    check(
        manifest["scene"]["model_sha256"] == file_sha256(MODEL_PATH),
        "baseline model hash mismatch",
    )
    check(
        manifest["acceptance_metrics"]["success"] is True,
        "baseline was not a successful physical grasp",
    )
    check(
        manifest["scope"]["sonic_closed_loop_replay_validated"] is False,
        "baseline scope must not overclaim SONIC replay",
    )
    return {
        "shape": list(frames.shape),
        "sha256": file_sha256(csv_path),
        "lifted_height_metres": manifest["acceptance_metrics"][
            "lifted_height_metres"
        ],
    }


def run_grasp(label, arguments, *, expected_success, generated):
    command = [
        sys.executable,
        str(REPO_ROOT / "runners/run_grasp.py"),
        "--headless",
        "--quiet",
        *arguments,
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    check(completed.returncode == 0, f"{label} failed:\n{completed.stdout}")
    result_match = RESULT_PATTERN.search(completed.stdout)
    control_match = CONTROL_PATTERN.search(completed.stdout)
    check(result_match is not None, f"{label}: missing RESULT line")
    check(control_match is not None, f"{label}: missing CONTROL line")
    success = result_match.group(1) == "True"
    if expected_success is not None:
        check(
            success is expected_success,
            f"{label}: unexpected success={success}",
        )
    control_mode = control_match.group(1)
    fixed_override = int(control_match.group(2))
    fixed_pd = int(control_match.group(3))
    window_count = int(control_match.group(4))
    window_changes = int(control_match.group(5))
    if generated:
        check(control_mode == "generated-motion", f"{label}: wrong mode")
        check(fixed_override == 0 and fixed_pd == 0, f"{label}: fixed arm used")
        check(window_count > 0 and window_changes > 0, f"{label}: static reference")
        check("[REFERENCE]" in completed.stdout, f"{label}: no reference evidence")
    else:
        check(control_mode == "keyframe", f"{label}: wrong mode")
    return {
        "success": success,
        "control_mode": control_mode,
        "fixed_arm_override_count": fixed_override,
        "fixed_arm_pd_write_count": fixed_pd,
        "reference_window_count": window_count,
        "reference_window_change_count": window_changes,
    }


def run_full_acceptance():
    common_generated = [
        "--duration",
        "2.0",
        "--source-fps",
        "50",
        "--close-start",
        "1.1",
        "--close-duration",
        "0.3",
        "--lift-start",
        "1.4",
        "--lift-duration",
        "0.4",
        "--allow-failure",
    ]
    return {
        "kimodo_sonic_smoke": run_grasp(
            "kimodo_sonic_smoke",
            [
                "--motion-source",
                "kimodo",
                "--motion-file",
                str(ASSET_DIR / "kimodo_walk_s0.csv"),
                *common_generated,
            ],
            expected_success=None,
            generated=True,
        ),
        "ardy_sonic_smoke": run_grasp(
            "ardy_sonic_smoke",
            [
                "--motion-source",
                "ardy",
                "--motion-file",
                str(ASSET_DIR / "ardy_final_s0.csv"),
                *common_generated,
            ],
            expected_success=None,
            generated=True,
        ),
        "keyframe_positive": run_grasp(
            "keyframe_positive",
            [],
            expected_success=True,
            generated=False,
        ),
        "keyframe_no_grip": run_grasp(
            "keyframe_no_grip",
            ["--no-grip", "--allow-failure"],
            expected_success=False,
            generated=False,
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="also run generated-motion smoke and physical positive/negative cases",
    )
    args = parser.parse_args()

    result = {
        "mode": "full" if args.full else "quick",
        "scene": validate_scene(),
        "loaders": validate_loaders(),
        "baseline": validate_baseline(),
    }
    if args.full:
        result["simulation"] = run_full_acceptance()
    print(json.dumps(result, indent=2, sort_keys=True))
    print("[ACCEPTANCE] PASS")


if __name__ == "__main__":
    main()
