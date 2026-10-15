import unittest

import numpy as np

from motion_adapter import (
    ISAACLAB_G1_29_JOINT_NAMES,
    MOTION_DOF,
    MotionTrajectory,
)


def valid_trajectory_kwargs(frame_count=3):
    timestamps = np.arange(frame_count, dtype=np.float64) / 50.0
    root_quat = np.zeros((frame_count, 4), dtype=np.float64)
    root_quat[:, 0] = 1.0
    return {
        "timestamps": timestamps,
        "root_pos": np.zeros((frame_count, 3), dtype=np.float64),
        "root_quat_wxyz": root_quat,
        "joint_pos": np.zeros((frame_count, MOTION_DOF), dtype=np.float64),
        "joint_vel": np.zeros((frame_count, MOTION_DOF), dtype=np.float64),
        "joint_names": ISAACLAB_G1_29_JOINT_NAMES,
        "source_fps": 50.0,
        "source": "test",
        "metadata": {"sample": "unit-test"},
    }


class MotionTrajectoryTest(unittest.TestCase):
    def make_trajectory(self, **overrides):
        values = valid_trajectory_kwargs()
        values.update(overrides)
        return MotionTrajectory(**values)

    def test_valid_contract_and_derived_properties(self):
        trajectory = self.make_trajectory(source="  kimodo  ")

        self.assertEqual(trajectory.frame_count, 3)
        self.assertAlmostEqual(trajectory.duration, 0.04)
        self.assertEqual(trajectory.source, "kimodo")
        self.assertEqual(trajectory.source_fps, 50.0)
        self.assertEqual(
            trajectory.joint_names, ISAACLAB_G1_29_JOINT_NAMES
        )
        self.assertEqual(trajectory.metadata["sample"], "unit-test")

    def test_single_frame_trajectory_has_zero_duration(self):
        trajectory = MotionTrajectory(**valid_trajectory_kwargs(frame_count=1))

        self.assertEqual(trajectory.frame_count, 1)
        self.assertEqual(trajectory.duration, 0.0)

    def test_arrays_are_copied_and_read_only(self):
        values = valid_trajectory_kwargs()
        original_joint_pos = values["joint_pos"]
        trajectory = MotionTrajectory(**values)

        original_joint_pos[0, 0] = 1.0
        self.assertEqual(trajectory.joint_pos[0, 0], 0.0)
        for array in (
            trajectory.timestamps,
            trajectory.root_pos,
            trajectory.root_quat_wxyz,
            trajectory.joint_pos,
            trajectory.joint_vel,
        ):
            self.assertFalse(array.flags.writeable)
        with self.assertRaises(ValueError):
            trajectory.joint_pos[0, 0] = 2.0
        with self.assertRaises(TypeError):
            trajectory.metadata["new"] = "value"

    def test_rejects_empty_or_invalid_shapes(self):
        cases = {
            "empty": {"timestamps": np.empty(0)},
            "timestamps": {"timestamps": np.zeros((3, 1))},
            "root_pos": {"root_pos": np.zeros((3, 4))},
            "root_quat": {"root_quat_wxyz": np.zeros((3, 3))},
            "joint_pos": {"joint_pos": np.zeros((3, MOTION_DOF - 1))},
            "joint_vel": {"joint_vel": np.zeros((2, MOTION_DOF))},
        }
        for name, overrides in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.make_trajectory(**overrides)

    def test_rejects_non_increasing_timestamps(self):
        for timestamps in (
            np.array([0.0, 0.0, 0.1]),
            np.array([0.0, 0.2, 0.1]),
        ):
            with self.subTest(timestamps=timestamps):
                with self.assertRaisesRegex(
                    ValueError, "strictly increasing"
                ):
                    self.make_trajectory(timestamps=timestamps)

    def test_rejects_non_finite_values(self):
        array_cases = {
            "timestamps": np.array([0.0, np.nan, 0.04]),
            "root_pos": np.full((3, 3), np.inf),
            "root_quat_wxyz": np.full((3, 4), np.nan),
            "joint_pos": np.full((3, MOTION_DOF), np.inf),
            "joint_vel": np.full((3, MOTION_DOF), np.nan),
        }
        for field, value in array_cases.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "finite"):
                    self.make_trajectory(**{field: value})

    def test_rejects_non_unit_quaternions(self):
        quaternions = np.zeros((3, 4), dtype=np.float64)
        quaternions[:, 0] = 2.0

        with self.assertRaisesRegex(ValueError, "unit quaternions"):
            self.make_trajectory(root_quat_wxyz=quaternions)

    def test_accepts_small_quaternion_norm_error(self):
        quaternions = np.zeros((3, 4), dtype=np.float64)
        quaternions[:, 0] = 1.0 + 0.5e-4

        trajectory = self.make_trajectory(root_quat_wxyz=quaternions)

        self.assertEqual(trajectory.frame_count, 3)

    def test_rejects_invalid_joint_names(self):
        duplicate = list(ISAACLAB_G1_29_JOINT_NAMES)
        duplicate[-1] = duplicate[0]
        wrong_order = list(ISAACLAB_G1_29_JOINT_NAMES)
        wrong_order[0], wrong_order[1] = wrong_order[1], wrong_order[0]
        cases = (
            ISAACLAB_G1_29_JOINT_NAMES[:-1],
            duplicate,
            wrong_order,
            [""] + list(ISAACLAB_G1_29_JOINT_NAMES[1:]),
            "not-a-name-sequence",
        )
        for names in cases:
            with self.subTest(names=names):
                with self.assertRaises(ValueError):
                    self.make_trajectory(joint_names=names)

    def test_rejects_invalid_source_metadata_and_fps(self):
        cases = (
            {"source": ""},
            {"source": 123},
            {"source_fps": 0.0},
            {"source_fps": -1.0},
            {"source_fps": np.nan},
            {"metadata": []},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    self.make_trajectory(**overrides)


if __name__ == "__main__":
    unittest.main()
