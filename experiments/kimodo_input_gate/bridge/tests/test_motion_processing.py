import logging
import unittest
from pathlib import Path

import numpy as np

from motion_adapter import (
    ISAACLAB_G1_29_JOINT_NAMES,
    MotionTrajectory,
    load_kimodo_csv,
    normalize_quaternion_sequence,
    prepare_trajectory,
    quaternion_yaw,
    register_root_frame,
    resample_trajectory,
    resample_trajectory_at,
)


FIXTURE_DIR = (
    Path(__file__).resolve().parents[1]
    / "server_reports/assets/kimodo_ardy_qpos"
)


def yaw_quaternion(angle):
    return np.array(
        [np.cos(angle / 2.0), 0.0, 0.0, np.sin(angle / 2.0)]
    )


def make_trajectory(
    timestamps,
    *,
    root_pos=None,
    root_quat=None,
    joint_pos=None,
):
    timestamps = np.asarray(timestamps, dtype=np.float64)
    frame_count = timestamps.shape[0]
    if root_pos is None:
        root_pos = np.zeros((frame_count, 3))
    if root_quat is None:
        root_quat = np.zeros((frame_count, 4))
        root_quat[:, 0] = 1.0
    if joint_pos is None:
        joint_pos = np.zeros((frame_count, 29))
    return MotionTrajectory(
        timestamps=timestamps,
        root_pos=root_pos,
        root_quat_wxyz=root_quat,
        joint_pos=joint_pos,
        joint_vel=np.zeros((frame_count, 29)),
        joint_names=ISAACLAB_G1_29_JOINT_NAMES,
        source_fps=50.0,
        source="processing-test",
        metadata={"fixture": "synthetic"},
    )


class MotionProcessingTest(unittest.TestCase):
    def test_quaternion_normalization_and_sign_continuity(self):
        quaternions = np.array(
            [
                [1.00005, 0.0, 0.0, 0.0],
                [-1.0, 0.0, 0.0, 0.0],
                [-0.92387953, 0.0, 0.0, -0.38268343],
            ]
        )

        normalized = normalize_quaternion_sequence(quaternions)

        np.testing.assert_allclose(
            np.linalg.norm(normalized, axis=1), 1.0, atol=1e-12
        )
        self.assertTrue(
            np.all(np.sum(normalized[:-1] * normalized[1:], axis=1) >= 0.0)
        )

    def test_slerp_known_midpoint(self):
        trajectory = make_trajectory(
            [0.0, 1.0],
            root_quat=np.stack(
                [yaw_quaternion(0.0), yaw_quaternion(np.pi / 2.0)]
            ),
        )

        result = resample_trajectory_at(
            trajectory,
            np.array([0.0, 0.5, 1.0]),
            target_fps=2.0,
        )

        self.assertAlmostEqual(
            quaternion_yaw(result.root_quat_wxyz[1]),
            np.pi / 4.0,
            places=12,
        )
        np.testing.assert_allclose(
            np.linalg.norm(result.root_quat_wxyz, axis=1),
            1.0,
            atol=1e-12,
        )

    def test_root_registration_normalizes_heading_and_position(self):
        source_pos = np.array(
            [[1.0, 2.0, 0.8], [1.0, 3.0, 0.8]]
        )
        source_quat = np.stack(
            [yaw_quaternion(np.pi / 2.0)] * 2
        )
        trajectory = make_trajectory(
            [0.0, 0.1],
            root_pos=source_pos,
            root_quat=source_quat,
        )

        registered = register_root_frame(
            trajectory,
            target_root_pos=[10.0, 20.0, 0.9],
            target_heading=0.0,
        )

        np.testing.assert_allclose(
            registered.root_pos,
            [[10.0, 20.0, 0.9], [11.0, 20.0, 0.9]],
            atol=1e-12,
        )
        self.assertAlmostEqual(
            quaternion_yaw(registered.root_quat_wxyz[0]), 0.0, places=12
        )
        self.assertTrue(
            registered.metadata["initial_heading_normalized"]
        )

    def test_linear_resampling_and_velocity_recomputation(self):
        timestamps = np.array([0.0, 0.5, 1.0])
        root_pos = np.column_stack(
            [2.0 * timestamps, -timestamps, np.full(3, 0.8)]
        )
        slopes = np.arange(1.0, 30.0)
        joint_pos = timestamps[:, None] * slopes[None, :]
        trajectory = make_trajectory(
            timestamps,
            root_pos=root_pos,
            joint_pos=joint_pos,
        )

        result = resample_trajectory(trajectory, target_fps=4.0)

        np.testing.assert_allclose(
            result.timestamps, [0.0, 0.25, 0.5, 0.75, 1.0]
        )
        np.testing.assert_allclose(
            result.root_pos[:, 0], 2.0 * result.timestamps
        )
        np.testing.assert_allclose(
            result.joint_pos,
            result.timestamps[:, None] * slopes[None, :],
        )
        np.testing.assert_allclose(
            result.joint_vel,
            np.broadcast_to(slopes, result.joint_vel.shape),
            atol=1e-12,
        )

    def test_static_trajectory_has_zero_velocity_and_exact_endpoints(self):
        trajectory = make_trajectory(
            [2.0, 2.4, 2.95],
            root_pos=np.repeat([[1.0, 2.0, 0.8]], 3, axis=0),
            joint_pos=np.repeat(
                np.arange(29, dtype=np.float64)[None, :] * 0.01,
                3,
                axis=0,
            ),
        )

        result = resample_trajectory(trajectory, target_fps=4.0)

        self.assertEqual(result.timestamps[0], 2.0)
        self.assertEqual(result.timestamps[-1], 2.95)
        self.assertTrue(np.all(np.diff(result.timestamps) > 0.0))
        self.assertLess(float(np.max(np.abs(result.joint_vel))), 1e-12)

    def test_reconstruction_at_source_samples(self):
        timestamps = np.array([0.0, 0.13, 0.51, 1.0])
        root_pos = np.column_stack(
            [timestamps, timestamps**2, 0.8 + 0.01 * timestamps]
        )
        joint_pos = np.sin(
            timestamps[:, None] * np.arange(1.0, 30.0)[None, :]
        )
        root_quat = np.stack(
            [yaw_quaternion(angle) for angle in (0.0, 0.2, 0.7, 1.1)]
        )
        root_quat[2] *= -1.0
        trajectory = make_trajectory(
            timestamps,
            root_pos=root_pos,
            root_quat=root_quat,
            joint_pos=joint_pos,
        )

        reconstructed = resample_trajectory_at(
            trajectory, trajectory.timestamps
        )

        np.testing.assert_allclose(reconstructed.root_pos, root_pos, atol=0.0)
        np.testing.assert_allclose(
            reconstructed.joint_pos, joint_pos, atol=0.0
        )
        orientation_dot = np.abs(
            np.sum(
                reconstructed.root_quat_wxyz
                * normalize_quaternion_sequence(root_quat),
                axis=1,
            )
        )
        np.testing.assert_allclose(orientation_dot, 1.0, atol=1e-12)

    def test_rejects_invalid_target_time_and_registration(self):
        trajectory = make_trajectory([0.0, 1.0])

        for target_fps in (0.0, -1.0, np.nan, np.inf, "bad"):
            with self.subTest(target_fps=target_fps):
                with self.assertRaisesRegex(ValueError, "target_fps"):
                    resample_trajectory(trajectory, target_fps)
        for timestamps in (
            np.array([-0.1, 0.5]),
            np.array([0.5, 1.1]),
            np.array([0.5, 0.5]),
            np.array([np.nan]),
        ):
            with self.subTest(timestamps=timestamps):
                with self.assertRaises(ValueError):
                    resample_trajectory_at(trajectory, timestamps)
        with self.assertRaisesRegex(ValueError, "target_root_pos"):
            register_root_frame(trajectory, [0.0, 0.0])
        with self.assertRaisesRegex(ValueError, "target_heading"):
            register_root_frame(
                trajectory,
                [0.0, 0.0, 0.8],
                target_heading=np.nan,
            )

    def test_real_trajectory_preparation(self):
        logging.disable(logging.WARNING)
        try:
            trajectory = load_kimodo_csv(
                FIXTURE_DIR / "kimodo_walk_s0.csv",
                source_fps=50.0,
            )
        finally:
            logging.disable(logging.NOTSET)

        prepared = prepare_trajectory(
            trajectory,
            target_fps=60.0,
            target_root_pos=[0.0, 0.0, 0.78874],
        )

        np.testing.assert_allclose(
            prepared.root_pos[0], [0.0, 0.0, 0.78874], atol=1e-12
        )
        self.assertAlmostEqual(
            quaternion_yaw(prepared.root_quat_wxyz[0]), 0.0, places=12
        )
        self.assertEqual(
            prepared.timestamps[0], trajectory.timestamps[0]
        )
        self.assertEqual(
            prepared.timestamps[-1], trajectory.timestamps[-1]
        )
        self.assertTrue(np.all(np.diff(prepared.timestamps) > 0.0))
        self.assertTrue(np.all(np.isfinite(prepared.joint_vel)))
        self.assertLess(
            float(
                np.max(
                    np.abs(
                        np.linalg.norm(
                            prepared.root_quat_wxyz, axis=1
                        )
                        - 1.0
                    )
                )
            ),
            1e-12,
        )
        self.assertTrue(
            np.all(
                np.sum(
                    prepared.root_quat_wxyz[:-1]
                    * prepared.root_quat_wxyz[1:],
                    axis=1,
                )
                >= 0.0
            )
        )


if __name__ == "__main__":
    unittest.main()
