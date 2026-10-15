import numpy as np
from collections import deque

from adapters.sonic_action_adapter import DEFAULT_ANGLES, M2I, I2M


def _quat_to_R(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


class SonicPolicyAdapter:
    """
    构造 g1_dyn 输入（994 维）：
      token_state(64)
      + his_base_ang_vel(10*3=30)      机体系角速度（MuJoCo qvel[3:6]）
      + his_joint_pos(10*29=290)       q - default，IsaacLab 序
      + his_joint_vel(10*29=290)       IsaacLab 序
      + his_last_action(10*29=290)     网络原始输出，IsaacLab 序
      + his_gravity_dir(10*3=30)       世界重力方向在机体系的表达
    各历史块内帧序为 oldest -> newest。
    """

    def __init__(self, cfg, model=None):
        self.cfg = cfg
        self.token_dim = cfg["observation"]["token_dim"]
        self.history_len = cfg["observation"]["history_len"]
        self.dof = cfg["robot"]["dof"]
        self._qpos_adr = None
        self._dof_adr = None
        if model is not None:
            joint_ids = np.asarray(model.actuator_trnid[:self.dof, 0], dtype=int)
            self._qpos_adr = np.asarray(model.jnt_qposadr[joint_ids], dtype=int)
            self._dof_adr = np.asarray(model.jnt_dofadr[joint_ids], dtype=int)

        self.default_isaac = np.array(
            [DEFAULT_ANGLES[I2M[i]] for i in range(self.dof)], dtype=np.float32
        )

        # 预热：全部 10 帧为静态站立初始值（重力 down，其余零）
        self.base_ang_vel_hist = deque(
            [np.zeros(3, np.float32)] * self.history_len, maxlen=self.history_len)
        self.body_joint_pos_hist = deque(
            [np.zeros(self.dof, np.float32)] * self.history_len, maxlen=self.history_len)
        self.body_joint_vel_hist = deque(
            [np.zeros(self.dof, np.float32)] * self.history_len, maxlen=self.history_len)
        self.last_action_hist = deque(
            [np.zeros(self.dof, np.float32)] * self.history_len, maxlen=self.history_len)
        self.gravity_dir_hist = deque(
            [np.array([0., 0., -1.], np.float32)] * self.history_len, maxlen=self.history_len)

    def build(self, data, token_state, last_action):
        token_state = np.asarray(token_state, dtype=np.float32).reshape(-1)
        if token_state.shape[0] != self.token_dim:
            raise ValueError(
                f"token_state dim mismatch: expected {self.token_dim}, got {token_state.shape[0]}"
            )

        last_action = np.asarray(last_action, dtype=np.float32).reshape(-1)
        if last_action.shape[0] != self.dof:
            raise ValueError(
                f"last_action dim mismatch: expected {self.dof}, got {last_action.shape[0]}"
            )

        qpos = np.asarray(data.qpos, dtype=np.float32)
        qvel = np.asarray(data.qvel, dtype=np.float32)

        base_ang_vel = qvel[3:6].copy()                       # 已是机体系
        if self._qpos_adr is None:
            qm = qpos[-self.dof:]
            vm = qvel[-self.dof:]
        else:
            qm = qpos[self._qpos_adr]
            vm = qvel[self._dof_adr]
        joint_pos = qm[I2M] - self.default_isaac
        joint_vel = vm[I2M]
        R = _quat_to_R(qpos[3:7])
        gravity_dir = (R.T @ np.array([0., 0., -1.], np.float32)).astype(np.float32)

        self.base_ang_vel_hist.append(base_ang_vel)
        self.body_joint_pos_hist.append(joint_pos)
        self.body_joint_vel_hist.append(joint_vel)
        self.last_action_hist.append(last_action)
        self.gravity_dir_hist.append(gravity_dir)

        obs = np.concatenate([
            token_state,
            np.concatenate(self.base_ang_vel_hist),
            np.concatenate(self.body_joint_pos_hist),
            np.concatenate(self.body_joint_vel_hist),
            np.concatenate(self.last_action_hist),
            np.concatenate(self.gravity_dir_hist),
        ], axis=0).astype(np.float32)

        if obs.shape[0] != 994:
            raise ValueError(f"policy_obs dim must be 994, got {obs.shape[0]}")

        return obs, {}
