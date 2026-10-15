import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from motion_adapter.baseline import (
    file_sha256,
    validate_baseline_frames,
    write_physical_grasp_baseline,
)
from motion_adapter.joint_contract import MUJOCO_G1_29_JOINT_NAMES


class BaselineArtifactTest(unittest.TestCase):
    @staticmethod
    def frames(frame_count=3):
        values = np.zeros((frame_count, 36), dtype=np.float64)
        values[:, 2] = 0.78874
        values[:, 3] = 1.0
        return values

    def test_rejects_invalid_shape_nonfinite_and_quaternion(self):
        with self.assertRaisesRegex(ValueError, "shape"):
            validate_baseline_frames(np.zeros((2, 35)))
        values = self.frames()
        values[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            validate_baseline_frames(values)
        values = self.frames()
        values[0, 3:7] = 0.0
        with self.assertRaisesRegex(ValueError, "unit length"):
            validate_baseline_frames(values)

    def test_writes_headerless_csv_and_self_consistent_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scene = root / "scene.xml"
            model = root / "model.xml"
            scene.write_text("<mujoco/>", encoding="utf-8")
            model.write_text("<mujoco model='g1'/>", encoding="utf-8")
            csv_path = root / "baseline.csv"
            manifest_path = root / "baseline.manifest.json"

            manifest = write_physical_grasp_baseline(
                csv_path,
                manifest_path,
                frames=self.frames(),
                source_fps=50.0,
                mujoco_joint_names=MUJOCO_G1_29_JOINT_NAMES,
                scene_path=scene,
                model_path=model,
                metrics={"success": True, "lifted_height_metres": 0.09},
                hand_control={"representation": "independent PD"},
                scene_objects={"cube": {"body": "red_cube"}},
                reproduction_command="python runners/run_grasp.py --headless",
            )

            loaded = np.loadtxt(csv_path, delimiter=",")
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded.shape, (3, 36))
            self.assertEqual(saved, manifest)
            self.assertEqual(saved["csv"]["sha256"], file_sha256(csv_path))
            self.assertEqual(saved["csv"]["shape"], [3, 36])
            self.assertEqual(len(saved["csv"]["joint_names"]), 29)
            self.assertFalse(saved["scope"]["csv_contains_hand_joints"])
            self.assertFalse(
                saved["scope"]["sonic_closed_loop_replay_validated"]
            )

    def test_refuses_failed_grasp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scene = root / "scene.xml"
            model = root / "model.xml"
            scene.write_text("<mujoco/>", encoding="utf-8")
            model.write_text("<mujoco/>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "successful"):
                write_physical_grasp_baseline(
                    root / "baseline.csv",
                    root / "baseline.json",
                    frames=self.frames(),
                    source_fps=50.0,
                    mujoco_joint_names=MUJOCO_G1_29_JOINT_NAMES,
                    scene_path=scene,
                    model_path=model,
                    metrics={"success": False},
                    hand_control={},
                    scene_objects={},
                    reproduction_command="test",
                )
            self.assertFalse((root / "baseline.csv").exists())


if __name__ == "__main__":
    unittest.main()
