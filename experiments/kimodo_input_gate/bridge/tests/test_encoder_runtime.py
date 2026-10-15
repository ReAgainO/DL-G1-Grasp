import argparse
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from adapters.sonic_encoder_adapter import SonicEncoderAdapter
from motion_adapter import (
    ISAACLAB_G1_29_JOINT_NAMES,
    SONIC_REFERENCE_DIM,
    MotionTrajectory,
    add_motion_arguments,
    load_motion_runtime,
)


FIXTURE_DIR = (
    Path(__file__).resolve().parents[1]
    / "server_reports/assets/kimodo_ardy_qpos"
)


def make_config():
    return {
        "robot": {"dof": 29},
        "observation": {
            "encoder_history_len": 10,
            "encoder_step": 5,
        },
    }


def make_trajectory(frame_count=80):
    timestamps = np.arange(frame_count, dtype=np.float64) / 50.0
    frame = np.arange(frame_count, dtype=np.float64)[:, None]
    joint = frame + np.arange(29, dtype=np.float64)[None, :] / 100.0
    root_quat = np.zeros((frame_count, 4), dtype=np.float64)
    root_quat[:, 0] = 1.0
    return MotionTrajectory(
        timestamps=timestamps,
        root_pos=np.zeros((frame_count, 3)),
        root_quat_wxyz=root_quat,
        joint_pos=joint,
        joint_vel=joint + 1000.0,
        joint_names=ISAACLAB_G1_29_JOINT_NAMES,
        source_fps=50.0,
        source="encoder-runtime-test",
        metadata={},
    )


class DummyData:
    def __init__(self, time=0.0):
        self.time = time
        self.qpos = np.zeros(36, dtype=np.float64)
        self.qpos[3] = 1.0


class EncoderRuntimeTest(unittest.TestCase):
    def test_static_mode_remains_640_values(self):
        adapter = SonicEncoderAdapter(make_config())

        obs = adapter.build()

        self.assertFalse(adapter.dynamic)
        self.assertEqual(sum(value.size for value in obs.values()), 640)
        self.assertEqual(
            adapter.window_log_line(),
            "reference_mode=static window_shape=(640,)",
        )

    def test_dynamic_time_progression_start_speed_and_content(self):
        trajectory = make_trajectory()
        adapter = SonicEncoderAdapter(
            make_config(),
            trajectory=trajectory,
            motion_start=0.2,
            motion_speed=2.0,
        )
        data = DummyData(time=0.1)

        before = adapter.build(data)
        self.assertEqual(adapter.last_reference_frame, 20)
        self.assertEqual(sum(value.size for value in before.values()), 640)
        np.testing.assert_array_equal(
            adapter.last_window.joint_velocities,
            trajectory.joint_vel[adapter.last_window.frame_indices] * 2.0,
        )

        data.time = 0.51
        after = adapter.build(data)
        self.assertEqual(adapter.last_reference_frame, 61)
        self.assertFalse(
            np.array_equal(
                before["motion_joint_positions_10frame_step5"],
                after["motion_joint_positions_10frame_step5"],
            )
        )
        self.assertIn("current_frame=61", adapter.window_log_line())
        self.assertIn(
            f"window_shape=({SONIC_REFERENCE_DIM},)",
            adapter.window_log_line(),
        )

    def test_tail_holds_last_and_explicit_time_overrides_data_time(self):
        trajectory = make_trajectory(frame_count=8)
        adapter = SonicEncoderAdapter(make_config(), trajectory=trajectory)
        data = DummyData(time=0.0)

        adapter.build(data, sim_time=100.0)

        self.assertEqual(adapter.last_reference_frame, 7)
        np.testing.assert_array_equal(
            adapter.last_window.frame_indices, np.full(10, 7)
        )
        self.assertTrue(
            np.all(np.isfinite(adapter.last_window.flatten()))
        )

    def test_rejects_invalid_encoder_and_timing_inputs(self):
        trajectory = make_trajectory()
        bad_cfg = make_config()
        bad_cfg["observation"]["encoder_step"] = 4
        with self.assertRaisesRegex(ValueError, "encoder_step=5"):
            SonicEncoderAdapter(bad_cfg)
        for start, speed in ((-1.0, 1.0), (0.0, 0.0), (0.0, np.nan)):
            with self.subTest(start=start, speed=speed):
                with self.assertRaises(ValueError):
                    SonicEncoderAdapter(
                        make_config(),
                        trajectory=trajectory,
                        motion_start=start,
                        motion_speed=speed,
                    )
        adapter = SonicEncoderAdapter(make_config(), trajectory=trajectory)
        with self.assertRaisesRegex(ValueError, "data.time"):
            adapter.build()
        with self.assertRaisesRegex(ValueError, "non-negative"):
            adapter.build(DummyData(), sim_time=-0.1)

    def test_cli_argument_names_and_group_validation(self):
        parser = argparse.ArgumentParser()
        add_motion_arguments(parser)
        args = parser.parse_args(
            [
                "--motion-source",
                "kimodo",
                "--motion-file",
                "motion.csv",
                "--source-fps",
                "30",
                "--motion-start",
                "1.5",
                "--motion-speed",
                "0.5",
            ]
        )
        self.assertEqual(args.motion_source, "kimodo")
        self.assertEqual(args.motion_file, "motion.csv")
        self.assertEqual(args.source_fps, 30.0)
        self.assertEqual(args.motion_start, 1.5)
        self.assertEqual(args.motion_speed, 0.5)

        partial = SimpleNamespace(
            motion_source="ardy",
            motion_file=None,
            source_fps=50.0,
            motion_start=0.0,
            motion_speed=1.0,
        )
        with self.assertRaisesRegex(ValueError, "provided together"):
            load_motion_runtime(
                partial,
                target_fps=50.0,
                target_root_pos=[0.0, 0.0, 0.8],
                target_heading=0.0,
            )

    def test_real_loader_runtime_and_log_identity(self):
        args = SimpleNamespace(
            motion_source="kimodo",
            motion_file=str(FIXTURE_DIR / "kimodo_walk_s0.csv"),
            source_fps=50.0,
            motion_start=0.25,
            motion_speed=1.5,
        )

        runtime = load_motion_runtime(
            args,
            target_fps=50.0,
            target_root_pos=[0.0, 0.0, 0.78874],
            target_heading=0.0,
        )
        log_line = runtime.startup_log_line()

        self.assertEqual(runtime.trajectory.frame_count, 120)
        self.assertIn("motion_source=kimodo", log_line)
        self.assertIn("loader=kimodo_loader", log_line)
        self.assertIn("source_frames=120", log_line)
        self.assertIn("source_fps=50", log_line)
        self.assertIn("prepared_frames=120", log_line)
        self.assertIn(
            "sha256=3381630edf823b80aee3c84da349d6874b2d160ff"
            "78252a0cbcbac309055c691",
            log_line,
        )


if __name__ == "__main__":
    unittest.main()
