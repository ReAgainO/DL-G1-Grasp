import hashlib
import tempfile
import unittest
from pathlib import Path

import numpy as np

from adapters.sonic_action_adapter import M2I
from motion_adapter import load_ardy_csv, load_kimodo_csv


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "server_reports/assets/kimodo_ardy_qpos"


def write_csv(path, values):
    np.savetxt(path, np.asarray(values), delimiter=",", fmt="%.17g")


def valid_qpos(frame_count=3):
    values = np.zeros((frame_count, 36), dtype=np.float64)
    values[:, 0] = np.arange(frame_count)
    values[:, 2] = 0.8
    values[:, 3] = 1.0
    values[:, 7:] = 0.001 * np.arange(frame_count)[:, None] * (
        np.arange(29)[None, :] + 1.0
    )
    return values


class MotionLoaderTest(unittest.TestCase):
    def test_source_specific_loaders_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "motion.csv"
            source = valid_qpos()
            write_csv(path, source)
            expected_sha = hashlib.sha256(path.read_bytes()).hexdigest()

            for loader, source_name, loader_name in (
                (load_kimodo_csv, "kimodo", "kimodo_loader"),
                (load_ardy_csv, "ardy", "ardy_loader"),
            ):
                with self.subTest(loader=loader_name):
                    with self.assertLogs(
                        "motion_adapter._csv_loader", level="INFO"
                    ) as logs:
                        trajectory = loader(path, source_fps=50.0)

                    self.assertEqual(trajectory.source, source_name)
                    self.assertEqual(trajectory.frame_count, 3)
                    self.assertEqual(trajectory.source_fps, 50.0)
                    self.assertEqual(
                        trajectory.metadata["loader"], loader_name
                    )
                    self.assertEqual(
                        trajectory.metadata["file_sha256"], expected_sha
                    )
                    self.assertEqual(trajectory.metadata["frame_count"], 3)
                    self.assertIn(f"loader={loader_name}", logs.output[0])
                    np.testing.assert_array_equal(
                        trajectory.root_pos, source[:, :3]
                    )
                    np.testing.assert_array_equal(
                        trajectory.root_quat_wxyz, source[:, 3:7]
                    )
                    np.testing.assert_array_equal(
                        trajectory.joint_pos[:, M2I], source[:, 7:]
                    )

    def test_timestamps_and_joint_velocities_use_explicit_fps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "linear.csv"
            source = valid_qpos(frame_count=4)
            write_csv(path, source)

            trajectory = load_kimodo_csv(path, source_fps=20.0)

            np.testing.assert_allclose(
                trajectory.timestamps, [0.0, 0.05, 0.1, 0.15]
            )
            expected_velocity_mujoco = np.broadcast_to(
                0.02 * (np.arange(29) + 1.0), (4, 29)
            )
            np.testing.assert_allclose(
                trajectory.joint_vel[:, M2I], expected_velocity_mujoco
            )

    def test_single_frame_velocity_is_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "single.csv"
            write_csv(path, valid_qpos(frame_count=1))

            trajectory = load_ardy_csv(path, source_fps=30.0)

            np.testing.assert_array_equal(
                trajectory.joint_vel, np.zeros((1, 29))
            )

    def test_real_fixture_matrix_and_round_trip(self):
        cases = (
            (
                load_kimodo_csv,
                "kimodo_walk_s0.csv",
                120,
                "3381630edf823b80aee3c84da349d6874b2d160ff78252a0cbcbac309055c691",
                0,
            ),
            (
                load_kimodo_csv,
                "test_pickup.csv",
                120,
                "a5dbebb3117a5ac11597be925d799508f833ce10238ead8c4ffdf8a10ad4aa55",
                18,
            ),
            (
                load_ardy_csv,
                "ardy_final_s0.csv",
                100,
                "2f1eba648efcc232b916a26bbf0f32774b99f7b95c8802f2194d65037dd659d0",
                0,
            ),
            (
                load_ardy_csv,
                "ardy_r5_sha4f_early.csv",
                200,
                "5d25c58dfc716f2d1d4e7adfbb17969ea6c7d11fea09d6764d582b0b9dd27edd",
                3,
            ),
        )
        for loader, file_name, frame_count, expected_sha, clip_count in cases:
            with self.subTest(file_name=file_name):
                path = FIXTURE_DIR / file_name
                source = np.loadtxt(path, delimiter=",", ndmin=2)

                if clip_count:
                    with self.assertLogs(
                        "motion_adapter._csv_loader", level="WARNING"
                    ) as logs:
                        trajectory = loader(path, source_fps=50.0)
                    self.assertEqual(len(logs.output), clip_count)
                else:
                    trajectory = loader(path, source_fps=50.0)

                self.assertEqual(trajectory.frame_count, frame_count)
                self.assertEqual(
                    trajectory.metadata["file_sha256"], expected_sha
                )
                self.assertEqual(
                    trajectory.metadata["joint_limit_clipping_count"],
                    clip_count,
                )
                for frame in (0, -1):
                    np.testing.assert_array_equal(
                        trajectory.root_pos[frame], source[frame, :3]
                    )
                    np.testing.assert_array_equal(
                        trajectory.root_quat_wxyz[frame], source[frame, 3:7]
                    )
                    np.testing.assert_array_equal(
                        trajectory.joint_pos[frame, M2I],
                        source[frame, 7:],
                    )

    def test_rejects_empty_wrong_columns_non_numeric_and_non_finite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cases = {
                "empty.csv": "",
                "wrong_columns.csv": ",".join(["0"] * 35) + "\n",
                "header.csv": ",".join(
                    ["root_x", "root_y", "root_z"]
                    + ["quat"] * 4
                    + ["joint"] * 29
                )
                + "\n",
                "nan.csv": ",".join(
                    ["nan"] + ["0"] * 2 + ["1"] + ["0"] * 32
                )
                + "\n",
                "blank_row.csv": ",".join(
                    ["0"] * 3 + ["1"] + ["0"] * 32
                )
                + "\n\n",
            }
            for file_name, contents in cases.items():
                with self.subTest(file_name=file_name):
                    path = temp_path / file_name
                    path.write_text(contents, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_kimodo_csv(path, source_fps=50.0)

    def test_rejects_missing_file_and_invalid_fps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "motion.csv"
            write_csv(path, valid_qpos())

            with self.assertRaises(FileNotFoundError):
                load_ardy_csv(path.with_name("missing.csv"), source_fps=50.0)

            for source_fps in (0, -1, np.nan, np.inf, "not-a-number", None):
                with self.subTest(source_fps=source_fps):
                    with self.assertRaises(ValueError):
                        load_ardy_csv(path, source_fps=source_fps)


if __name__ == "__main__":
    unittest.main()
