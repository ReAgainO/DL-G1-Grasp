import numpy as np

from adapters.sonic_action_adapter import I2M, DEFAULT_ANGLES
from motion_adapter.reference_window import (
    SONIC_REFERENCE_DIM,
    SonicReferenceWindow,
    build_sonic_reference_window,
)
from motion_adapter.trajectory import MotionTrajectory


class SonicEncoderAdapter:
    """
    构造 g1 encoder 输入（640 维），块布局（实测自 checkpoint 权重）：
      motion_joint_velocities_10frame_step5 : 10 * 29 = 290
      motion_joint_positions_10frame_step5  : 10 * 29 = 290
      motion_anchor_orientation_10frame_step5: 10 * 6 = 60

    未提供 trajectory 时保持原地站立静态参考；提供 trajectory 后，
    根据仿真时间生成动态参考窗口。
    """

    def __init__(
        self,
        cfg,
        trajectory=None,
        *,
        motion_start=0.0,
        motion_speed=1.0,
    ):
        self.cfg = cfg
        self.history_len = cfg["observation"]["encoder_history_len"]
        self.encoder_step = cfg["observation"].get("encoder_step", 5)
        self.dof = cfg["robot"]["dof"]
        if self.history_len != 10 or self.encoder_step != 5:
            raise ValueError(
                "SONIC encoder requires encoder_history_len=10 and "
                "encoder_step=5"
            )
        if self.dof != 29:
            raise ValueError("SONIC encoder requires robot.dof=29")
        if trajectory is not None and not isinstance(
            trajectory, MotionTrajectory
        ):
            raise TypeError("trajectory must be a MotionTrajectory or None")
        try:
            motion_start = float(motion_start)
            motion_speed = float(motion_speed)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "motion_start and motion_speed must be finite numbers"
            ) from exc
        if not np.isfinite(motion_start) or motion_start < 0.0:
            raise ValueError("motion_start must be a finite non-negative number")
        if not np.isfinite(motion_speed) or motion_speed <= 0.0:
            raise ValueError("motion_speed must be a finite positive number")

        self.trajectory = trajectory
        self.motion_start = motion_start
        self.motion_speed = motion_speed
        self.last_window = None
        self.last_sim_time = None
        self.last_motion_time = None
        self.last_reference_frame = None

        default_isaac = np.array(
            [DEFAULT_ANGLES[I2M[i]] for i in range(self.dof)], dtype=np.float32
        )
        self._static_encoder_obs = {
            "motion_joint_positions_10frame_step5":
                np.tile(default_isaac, self.history_len),
            "motion_joint_velocities_10frame_step5":
                np.zeros(self.history_len * self.dof, dtype=np.float32),
            "motion_anchor_orientation_10frame_step5":
                np.tile(np.array([1., 0., 0., 1., 0., 0.], np.float32),
                        self.history_len),
        }

    @property
    def dynamic(self):
        return self.trajectory is not None

    def _resolve_sim_time(self, data, sim_time):
        if sim_time is None:
            if data is None or not hasattr(data, "time"):
                raise ValueError(
                    "dynamic encoder requires data.time or explicit sim_time"
                )
            sim_time = data.time
        try:
            sim_time = float(sim_time)
        except (TypeError, ValueError) as exc:
            raise ValueError("sim_time must be a finite non-negative number") from exc
        if not np.isfinite(sim_time) or sim_time < 0.0:
            raise ValueError("sim_time must be a finite non-negative number")
        return sim_time

    def _resolve_anchor_quaternion(self, data):
        if data is None or not hasattr(data, "qpos"):
            raise ValueError("dynamic encoder requires data.qpos for anchor")
        qpos = np.asarray(data.qpos, dtype=np.float64)
        if qpos.ndim != 1 or qpos.shape[0] < 7:
            raise ValueError("data.qpos must contain a root quaternion at [3:7]")
        anchor = qpos[3:7]
        if not np.all(np.isfinite(anchor)):
            raise ValueError("data.qpos root quaternion contains NaN or Inf")
        return anchor

    def build(self, data=None, *, sim_time=None):
        if not self.dynamic:
            return self._static_encoder_obs

        sim_time = self._resolve_sim_time(data, sim_time)
        motion_time = (
            float(self.trajectory.timestamps[0])
            + self.motion_start
            + sim_time * self.motion_speed
        )
        current_frame = int(
            np.searchsorted(
                self.trajectory.timestamps,
                motion_time + 1e-10,
                side="right",
            )
            - 1
        )
        current_frame = int(
            np.clip(current_frame, 0, self.trajectory.frame_count - 1)
        )
        window = build_sonic_reference_window(
            self.trajectory,
            current_frame,
            anchor_quat_wxyz=self._resolve_anchor_quaternion(data),
        )
        if self.motion_speed != 1.0:
            window = SonicReferenceWindow(
                requested_indices=window.requested_indices,
                frame_indices=window.frame_indices,
                joint_velocities=(
                    window.joint_velocities * self.motion_speed
                ),
                joint_positions=window.joint_positions,
                anchor_orientation_6d=window.anchor_orientation_6d,
            )
        encoder_obs = window.as_encoder_obs()
        if sum(value.size for value in encoder_obs.values()) != SONIC_REFERENCE_DIM:
            raise RuntimeError("dynamic SONIC encoder output must contain 640 values")

        self.last_window = window
        self.last_sim_time = sim_time
        self.last_motion_time = motion_time
        self.last_reference_frame = current_frame
        return encoder_obs

    def window_log_line(self):
        if self.last_window is None:
            return "reference_mode=static window_shape=(640,)"
        requested = self.last_window.requested_indices
        actual = self.last_window.frame_indices
        return (
            "reference_mode=dynamic "
            f"sim_time={self.last_sim_time:.6f} "
            f"motion_time={self.last_motion_time:.6f} "
            f"current_frame={self.last_reference_frame} "
            f"requested_frames={int(requested[0])}:{int(requested[-1])} "
            f"actual_frames={int(actual[0])}:{int(actual[-1])} "
            f"window_shape=({SONIC_REFERENCE_DIM},)"
        )
