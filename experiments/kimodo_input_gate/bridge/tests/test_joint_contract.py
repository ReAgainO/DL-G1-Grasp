import tempfile
import unittest
from pathlib import Path

import numpy as np

from adapters.sonic_action_adapter import I2M
from motion_adapter import (
    DEFAULT_G1_MODEL_XML,
    ISAACLAB_G1_29_JOINT_NAMES,
    MUJOCO_G1_29_JOINT_NAMES,
    isaac_to_mujoco,
    load_kimodo_csv,
    load_model_joint_contract,
    mujoco_to_isaac,
)


def valid_qpos():
    values = np.zeros((2, 36), dtype=np.float64)
    values[:, 2] = 0.8
    values[:, 3] = 1.0
    return values


class JointContractTest(unittest.TestCase):
    def test_model_contract_matches_expected_skeleton_and_ranges(self):
        names, limits, model_path, model_sha256 = (
            load_model_joint_contract()
        )

        self.assertEqual(names, MUJOCO_G1_29_JOINT_NAMES)
        self.assertEqual(limits.shape, (29, 2))
        self.assertTrue(np.all(limits[:, 0] < limits[:, 1]))
        self.assertFalse(limits.flags.writeable)
        self.assertEqual(model_path, DEFAULT_G1_MODEL_XML.resolve())
        self.assertEqual(len(model_sha256), 64)

    def test_mapping_round_trip_is_exact(self):
        values = np.random.default_rng(7).normal(size=(13, 29))

        canonical = mujoco_to_isaac(values)
        reconstructed = isaac_to_mujoco(canonical)

        self.assertLess(
            float(np.max(np.abs(values - reconstructed))), 1e-6
        )
        self.assertEqual(
            tuple(MUJOCO_G1_29_JOINT_NAMES[index] for index in I2M),
            ISAACLAB_G1_29_JOINT_NAMES,
        )

    def test_loader_rejects_wrong_source_joint_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "motion.csv"
            np.savetxt(path, valid_qpos(), delimiter=",")
            wrong_names = list(MUJOCO_G1_29_JOINT_NAMES)
            wrong_names[0], wrong_names[1] = wrong_names[1], wrong_names[0]

            with self.assertRaisesRegex(ValueError, "skeleton/order"):
                load_kimodo_csv(
                    path,
                    50.0,
                    source_joint_names=wrong_names,
                )

    def test_loader_rejects_model_with_wrong_actuator_skeleton(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            motion_path = temp_path / "motion.csv"
            model_path = temp_path / "wrong_model.xml"
            np.savetxt(motion_path, valid_qpos(), delimiter=",")
            model_xml = DEFAULT_G1_MODEL_XML.read_text(encoding="utf-8")
            old = (
                '<motor name="left_hip_pitch" '
                'joint="left_hip_pitch_joint"'
            )
            new = '<motor name="left_hip_pitch" joint="wrong_joint"'
            self.assertIn(old, model_xml)
            model_path.write_text(
                model_xml.replace(old, new, 1),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "skeleton/order"):
                load_kimodo_csv(
                    motion_path,
                    50.0,
                    model_xml_path=model_path,
                )

    def test_small_limit_excess_is_logged_and_clipped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "slight_excess.csv"
            values = valid_qpos()
            waist_pitch_mujoco_index = (
                MUJOCO_G1_29_JOINT_NAMES.index("waist_pitch_joint")
            )
            values[1, 7 + waist_pitch_mujoco_index] = 0.5205
            np.savetxt(path, values, delimiter=",")

            with self.assertLogs(
                "motion_adapter._csv_loader", level="WARNING"
            ) as logs:
                trajectory = load_kimodo_csv(
                    path,
                    50.0,
                    joint_limit_tolerance=0.001,
                )

            waist_pitch_isaac_index = (
                ISAACLAB_G1_29_JOINT_NAMES.index("waist_pitch_joint")
            )
            self.assertEqual(
                trajectory.joint_pos[1, waist_pitch_isaac_index], 0.52
            )
            self.assertEqual(
                trajectory.metadata["joint_limit_clipping_count"], 1
            )
            record = trajectory.metadata["joint_limit_clipping"][0]
            self.assertEqual(record["frame"], 1)
            self.assertEqual(record["joint"], "waist_pitch_joint")
            self.assertAlmostEqual(record["excess"], 0.0005)
            self.assertIn("frame=1", logs.output[0])
            self.assertIn("joint=waist_pitch_joint", logs.output[0])

    def test_large_limit_excess_is_rejected_with_location(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "large_excess.csv"
            values = valid_qpos()
            waist_pitch_mujoco_index = (
                MUJOCO_G1_29_JOINT_NAMES.index("waist_pitch_joint")
            )
            values[1, 7 + waist_pitch_mujoco_index] = 0.55
            np.savetxt(path, values, delimiter=",")

            with self.assertRaisesRegex(
                ValueError,
                r"large_excess\.csv.*frame=1 "
                r"joint=waist_pitch_joint.*excess=0\.03",
            ):
                load_kimodo_csv(
                    path,
                    50.0,
                    joint_limit_tolerance=0.02,
                )

    def test_loader_rejects_invalid_tolerance_and_missing_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "motion.csv"
            np.savetxt(path, valid_qpos(), delimiter=",")

            for tolerance in (-1.0, np.nan, np.inf, "invalid"):
                with self.subTest(tolerance=tolerance):
                    with self.assertRaisesRegex(
                        ValueError, "joint_limit_tolerance"
                    ):
                        load_kimodo_csv(
                            path,
                            50.0,
                            joint_limit_tolerance=tolerance,
                        )

            with self.assertRaises(FileNotFoundError):
                load_kimodo_csv(
                    path,
                    50.0,
                    model_xml_path=path.with_name("missing.xml"),
                )


if __name__ == "__main__":
    unittest.main()
