import numpy as np


# ---------------------------------------------------------------------------
# G1 29-DoF 常量（与官方 SONIC 部署代码 policy_parameters.hpp 一致）
# 注意：以下映射数组的"行为"（索引方向）与仓库命名相反，已实测确认。
# ---------------------------------------------------------------------------

# mujoco 关节序 -> IsaacLab 网络序
M2I = [0, 3, 6, 9, 13, 17, 1, 4, 7, 10, 14, 18,
       2, 5, 8, 11, 15, 19, 21, 23, 25, 27,
       12, 16, 20, 22, 24, 26, 28]
# IsaacLab 网络序 -> mujoco 关节序
I2M = [0] * 29
for _m, _i in enumerate(M2I):
    I2M[_i] = _m

# default 关节角（mujoco 序）
DEFAULT_ANGLES = np.zeros(29, dtype=np.float64)
for _k, _v in {
    0: -0.312, 3: 0.669, 4: -0.363,       # 左腿
    6: -0.312, 9: 0.669, 10: -0.363,        # 右腿
    15: 0.2, 16: 0.2, 18: 0.6,              # 左臂
    22: 0.2, 23: -0.2, 25: 0.6,             # 右臂
}.items():
    DEFAULT_ANGLES[_k] = _v

# 电机臂参数（来自 gear_sonic robots/g1.py）
_ARM_5020 = 0.003609725
_ARM_7520_14 = 0.010177520
_ARM_7520_22 = 0.025101925
_ARM_4010 = 0.00425
_WN = 10 * 2 * np.pi

# 每个 mujoco 关节对应的电机类型（臂参数）
_JOINT_ARM = np.zeros(29)
for _m in (0, 1, 3, 6, 7, 9):
    _JOINT_ARM[_m] = _ARM_7520_22
for _m in (2, 8, 12):
    _JOINT_ARM[_m] = _ARM_7520_14
for _m in (4, 5, 10, 11, 13, 14):
    _JOINT_ARM[_m] = 2 * _ARM_5020
for _m in range(15, 29):
    _JOINT_ARM[_m] = _ARM_4010 if _m in (20, 21, 27, 28) else _ARM_5020

# effort limit（mujoco 序）
EFFORT_LIMIT = np.zeros(29)
for _m in (0, 1, 3, 6, 7, 9):
    EFFORT_LIMIT[_m] = 139
for _m in (2, 8, 12):
    EFFORT_LIMIT[_m] = 88
for _m in (4, 5, 10, 11, 13, 14):
    EFFORT_LIMIT[_m] = 50
for _m in range(15, 29):
    EFFORT_LIMIT[_m] = 5 if _m in (20, 21, 27, 28) else 25

# PD 增益：kp = arm * wn^2，kd = 4 * arm * wn
KP = _JOINT_ARM * _WN ** 2
KD = 4 * _JOINT_ARM * _WN

# 每个关节的动作缩放：action_scale = 0.25 * effort / kp
ACTION_SCALE = 0.25 * EFFORT_LIMIT / KP

# default 姿态下双脚恰好接触地面时的基座高度
STAND_INIT_HEIGHT = 0.788740


class SonicActionAdapter:
    """
    策略输出语义（官方部署代码 CreatePolicyCommand）：
      网络输出 raw 为 IsaacLab 顺序的关节位置偏移（配合 per-joint action_scale）。
      关节目标：q_target[m] = default[m] + raw[M2I[m]] * ACTION_SCALE[m]
      每个物理子步用 PD 计算力矩：tau = kp*(q_target - q) - kd*dq
    """

    def __init__(self, cfg, model=None):
        self.cfg = cfg
        self.action_dim = cfg["robot"]["dof"]
        self._jnt_range = None
        self._qpos_adr = None
        self._dof_adr = None
        if model is not None:
            joint_ids = np.asarray(model.actuator_trnid[:self.action_dim, 0], dtype=int)
            self._qpos_adr = np.asarray(model.jnt_qposadr[joint_ids], dtype=int)
            self._dof_adr = np.asarray(model.jnt_dofadr[joint_ids], dtype=int)
            self._jnt_range = np.asarray(model.jnt_range[joint_ids])
            self._ctrl_range = np.asarray(model.actuator_ctrlrange[:self.action_dim])
        # 启动阶段目标保持在 default
        self._target = DEFAULT_ANGLES.copy()

    def set_action(self, raw_isaac):
        """50Hz 调用：把 IsaacLab 顺序的网络原始输出转成 mujoco 顺序的关节目标。"""
        raw_isaac = np.asarray(raw_isaac, dtype=np.float64).reshape(-1)
        if raw_isaac.shape[0] != self.action_dim:
            raise ValueError(
                f"action dim mismatch: expected {self.action_dim}, got {raw_isaac.shape[0]}"
            )
        target = np.array(
            [DEFAULT_ANGLES[m] + raw_isaac[M2I[m]] * ACTION_SCALE[m]
             for m in range(self.action_dim)]
        )
        if self._jnt_range is not None:
            target = np.clip(target, self._jnt_range[:, 0], self._jnt_range[:, 1])
        self._target = target
        return self._target

    def override_targets(self, actuator_indices, target_positions):
        """覆盖少量 MuJoCo 执行器顺序的关节目标，用于手臂任务轨迹。"""
        indices = np.asarray(actuator_indices, dtype=int)
        targets = np.asarray(target_positions, dtype=np.float64)
        if indices.shape != targets.shape:
            raise ValueError(
                f"override shape mismatch: indices={indices.shape}, targets={targets.shape}"
            )
        self._target[indices] = targets
        if self._jnt_range is not None:
            self._target[indices] = np.clip(
                self._target[indices],
                self._jnt_range[indices, 0],
                self._jnt_range[indices, 1],
            )

    def step_pd(self, data):
        """每个物理子步调用：根据当前目标用 PD 计算力矩并写入 data.ctrl。"""
        if self._qpos_adr is None:
            q = np.asarray(data.qpos[-self.action_dim:], dtype=np.float64)
            v = np.asarray(data.qvel[-self.action_dim:], dtype=np.float64)
        else:
            q = np.asarray(data.qpos[self._qpos_adr], dtype=np.float64)
            v = np.asarray(data.qvel[self._dof_adr], dtype=np.float64)
        tau = KP * (self._target - q) - KD * v
        if self._ctrl_range is not None:
            tau = np.clip(tau, self._ctrl_range[:, 0], self._ctrl_range[:, 1])
        data.ctrl[: self.action_dim] = tau
