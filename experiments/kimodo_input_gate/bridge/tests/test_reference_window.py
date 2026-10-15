import hashlib
import unittest

import numpy as np

from adapters.sonic_action_adapter import DEFAULT_ANGLES, I2M
from adapters.sonic_encoder_adapter import SonicEncoderAdapter
from motion_adapter import (
    ANCHOR_ORIENTATION_KEY,
    ISAACLAB_G1_29_JOINT_NAMES,
    JOINT_POSITION_KEY,
    JOINT_VELOCITY_KEY,
    SONIC_REFERENCE_DIM,
    MotionTrajectory,
    build_sonic_reference_window,
    quaternion_to_anchor_6d,
)


def yaw_quaternion(angle):
    return np.array(
        [np.cos(angle / 2.0), 0.0, 0.0, np.sin(angle / 2.0)]
    )


def dynamic_trajectory(frame_count=100):
    timestamps = np.arange(frame_count, dtype=np.float64) / 50.0
    frame_values = np.arange(frame_count, dtype=np.float64)[:, None]
    joint_offsets = np.arange(29, dtype=np.float64)[None, :] / 100.0
    joint_pos = frame_values + joint_offsets
    joint_vel = 1000.0 + joint_pos
    root_quat = np.stack(
        [yaw_quaternion(0.01 * frame) for frame in range(frame_count)]
    )
    return MotionTrajectory(
        timestamps=timestamps,
        root_pos=np.zeros((frame_count, 3)),
        root_quat_wxyz=root_quat,
        joint_pos=joint_pos,
        joint_vel=joint_vel,
        joint_names=ISAACLAB_G1_29_JOINT_NAMES,
        source_fps=50.0,
        source="reference-window-test",
        metadata={},
    )


class ReferenceWindowTest(unittest.TestCase):
    def test_first_and_middle_window_indices(self):
        trajectory = dynamic_trajectory()
        anchor = yaw_quaternion(0.0)

        first = build_sonic_reference_window(
            trajectory, 0, anchor_quat_wxyz=anchor
        )
        middle = build_sonic_reference_window(
            trajectory, 17, anchor_quat_wxyz=anchor
        )

        np.testing.assert_array_equal(
            first.requested_indices,
            np.arange(0, 50, 5),
        )
        np.testing.assert_array_equal(
            first.frame_indices,
            np.arange(0, 50, 5),
        )
        np.testing.assert_array_equal(
            middle.frame_indices,
            17 + np.arange(0, 50, 5),
        )
        np.testing.assert_array_equal(
            first.joint_positions,
            trajectory.joint_pos[first.frame_indices],
        )
        np.testing.assert_array_equal(
            first.joint_velocities,
            trajectory.joint_vel[first.frame_indices],
        )

    def test_tail_window_uses_hold_last(self):
        trajectory = dynamic_trajectory(frame_count=20)

        window = build_sonic_reference_window(
            trajectory,
            18,
            anchor_quat_wxyz=trajectory.root_quat_wxyz[18],
        )

        np.testing.assert_array_equal(
            window.requested_indices,
            18 + np.arange(0, 50, 5),
        )
        np.testing.assert_array_equal(
            window.frame_indices,
            [18, 19, 19, 19, 19, 19, 19, 19, 19, 19],
        )
        np.testing.assert_array_equal(
            window.joint_positions[1:],
            np.repeat(trajectory.joint_pos[[-1]], 9, axis=0),
        )

    def test_window_after_trajectory_end_holds_last_frame(self):
        trajectory = dynamic_trajectory(frame_count=8)

        window = build_sonic_reference_window(
            trajectory,
            20,
            anchor_quat_wxyz=trajectory.root_quat_wxyz[-1],
        )

        np.testing.assert_array_equal(
            window.frame_indices, np.full(10, 7)
        )
        np.testing.assert_array_equal(
            window.joint_velocities,
            np.repeat(trajectory.joint_vel[[-1]], 10, axis=0),
        )

    def test_encoder_shapes_flatten_order_and_dimension(self):
        trajectory = dynamic_trajectory()
        window = build_sonic_reference_window(
            trajectory,
            3,
            anchor_quat_wxyz=yaw_quaternion(0.0),
        )

        encoder_obs = window.as_encoder_obs()
        flattened = window.flatten()

        self.assertEqual(encoder_obs[JOINT_VELOCITY_KEY].shape, (290,))
        self.assertEqual(encoder_obs[JOINT_POSITION_KEY].shape, (290,))
        self.assertEqual(encoder_obs[ANCHOR_ORIENTATION_KEY].shape, (60,))
        self.assertEqual(flattened.shape, (SONIC_REFERENCE_DIM,))
        self.assertEqual(SONIC_REFERENCE_DIM, 640)
        np.testing.assert_array_equal(
            flattened[:290], encoder_obs[JOINT_VELOCITY_KEY]
        )
        np.testing.assert_array_equal(
            flattened[290:580], encoder_obs[JOINT_POSITION_KEY]
        )
        np.testing.assert_array_equal(
            flattened[580:], encoder_obs[ANCHOR_ORIENTATION_KEY]
        )

    def test_anchor_orientation_uses_relative_first_two_columns(self):
        reference = np.stack(
            [yaw_quaternion(0.0), yaw_quaternion(np.pi / 2.0)]
        )

        orientation = quaternion_to_anchor_6d(
            reference,
            anchor_quat_wxyz=yaw_quaternion(0.0),
        )
        relative_identity = quaternion_to_anchor_6d(
            reference[[1]],
            anchor_quat_wxyz=reference[1],
        )

        np.testing.assert_allclose(
            orientation[0], [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        )
        np.testing.assert_allclose(
            orientation[1], [0.0, -1.0, 1.0, 0.0, 0.0, 0.0],
            atol=1e-12,
        )
        np.testing.assert_allclose(
            relative_identity[0],
            [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            atol=1e-12,
        )

    def test_dynamic_windows_have_different_hashes(self):
        trajectory = dynamic_trajectory()
        hashes = []
        for current_frame in (0, 1, 10):
            window = build_sonic_reference_window(
                trajectory,
                current_frame,
                anchor_quat_wxyz=trajectory.root_quat_wxyz[current_frame],
            )
            hashes.append(
                hashlib.sha256(window.flatten().tobytes()).hexdigest()
            )

        self.assertEqual(len(set(hashes)), len(hashes))

    def test_static_window_matches_legacy_encoder_adapter(self):
        cfg = {
            "robot": {"dof": 29},
            "observation": {"encoder_history_len": 10},
        }
        legacy = SonicEncoderAdapter(cfg).build()
        default_isaac = np.asarray(
            [DEFAULT_ANGLES[I2M[index]] for index in range(29)],
            dtype=np.float64,
        )
        frame_count = 50
        root_quat = np.zeros((frame_count, 4))
        root_quat[:, 0] = 1.0
        trajectory = MotionTrajectory(
            timestamps=np.arange(frame_count) / 50.0,
            root_pos=np.zeros((frame_count, 3)),
            root_quat_wxyz=root_quat,
            joint_pos=np.repeat(
                default_isaac[None, :], frame_count, axis=0
            ),
            joint_vel=np.zeros((frame_count, 29)),
            joint_names=ISAACLAB_G1_29_JOINT_NAMES,
            source_fps=50.0,
            source="static-compatibility-test",
            metadata={},
        )

        generated = build_sonic_reference_window(
            trajectory,
            0,
            anchor_quat_wxyz=np.array([1.0, 0.0, 0.0, 0.0]),
        ).as_encoder_obs()

        self.assertEqual(set(generated), set(legacy))
        for key in legacy:
            with self.subTest(key=key):
                np.testing.assert_array_equal(generated[key], legacy[key])

    def test_rejects_invalid_frame_and_anchor(self):
        trajectory = dynamic_trajectory()

        for current_frame in (-1, 1.5, True):
            with self.subTest(current_frame=current_frame):
                with self.assertRaisesRegex(ValueError, "current_frame"):
                    build_sonic_reference_window(
                        trajectory,
                        current_frame,
                        anchor_quat_wxyz=yaw_quaternion(0.0),
                    )
        for anchor in (
            np.array([1.0, 0.0, 0.0]),
            np.zeros(4),
            np.array([np.nan, 0.0, 0.0, 0.0]),
        ):
            with self.subTest(anchor=anchor):
                with self.assertRaises(ValueError):
                    build_sonic_reference_window(
                        trajectory,
                        0,
                        anchor_quat_wxyz=anchor,
                    )


if __name__ == "__main__":
    unittest.main()
