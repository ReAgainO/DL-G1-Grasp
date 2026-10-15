import unittest
from unittest.mock import patch

import numpy as np

from runners.run_grasp import (
    RIGHT_HAND_CLOSED,
    RIGHT_HAND_OPEN,
    grasp_targets,
)


class GraspControlModeTest(unittest.TestCase):
    def test_generated_motion_uses_short_trajectory_phase_timing(self):
        expected = (
            (0.5, "motion"),
            (1.1, "close"),
            (1.4, "lift"),
            (2.2, "hold"),
        )
        for time_s, expected_phase in expected:
            with self.subTest(time_s=time_s):
                phase, arm, _ = grasp_targets(
                    time_s,
                    False,
                    RIGHT_HAND_OPEN,
                    RIGHT_HAND_CLOSED,
                    1.1,
                    0.3,
                    0.0,
                    1.4,
                    0.8,
                    generated_motion=True,
                )
                self.assertEqual(phase, expected_phase)
                self.assertIsNone(arm)

    def test_generated_motion_does_not_read_keyframe_arm_target(self):
        with patch(
            "runners.run_grasp.keyframe_arm_target",
            side_effect=AssertionError("fixed keyframe path was used"),
        ):
            phase, arm, hand = grasp_targets(
                6.0,
                False,
                RIGHT_HAND_OPEN,
                RIGHT_HAND_CLOSED,
                12.0,
                2.0,
                0.0,
                14.0,
                3.0,
                generated_motion=True,
            )

        self.assertEqual(phase, "motion")
        self.assertIsNone(arm)
        np.testing.assert_array_equal(hand, RIGHT_HAND_OPEN)

    def test_keyframe_mode_still_uses_arm_target(self):
        sentinel = np.arange(7, dtype=np.float64)
        with patch(
            "runners.run_grasp.keyframe_arm_target",
            return_value=sentinel,
        ) as keyframe_target:
            phase, arm, _ = grasp_targets(
                6.0,
                False,
                RIGHT_HAND_OPEN,
                RIGHT_HAND_CLOSED,
                12.0,
                2.0,
                0.0,
                14.0,
                3.0,
                generated_motion=False,
            )

        self.assertEqual(phase, "move_over")
        self.assertIs(arm, sentinel)
        keyframe_target.assert_called_once()

    def test_hand_timing_is_independent_of_body_control_mode(self):
        generated = grasp_targets(
            13.0,
            False,
            RIGHT_HAND_OPEN,
            RIGHT_HAND_CLOSED,
            12.0,
            2.0,
            0.0,
            14.0,
            3.0,
            generated_motion=True,
        )
        keyframe = grasp_targets(
            13.0,
            False,
            RIGHT_HAND_OPEN,
            RIGHT_HAND_CLOSED,
            12.0,
            2.0,
            0.0,
            14.0,
            3.0,
            generated_motion=False,
        )
        no_grip = grasp_targets(
            13.0,
            True,
            RIGHT_HAND_OPEN,
            RIGHT_HAND_CLOSED,
            12.0,
            2.0,
            0.0,
            14.0,
            3.0,
            generated_motion=True,
        )

        self.assertEqual(generated[0], "close")
        np.testing.assert_array_equal(generated[2], keyframe[2])
        np.testing.assert_array_equal(no_grip[2], RIGHT_HAND_OPEN)
        self.assertFalse(np.array_equal(generated[2], RIGHT_HAND_OPEN))


if __name__ == "__main__":
    unittest.main()
