# Kimodo / ARDY Motion Integration Plan

## 目标

将 Kimodo 和 ARDY 输出的 G1 MuJoCo qpos CSV 转换为统一运动轨迹，
生成 SONIC 所需的 10 帧 step5 参考窗口，并用生成轨迹替换抓取流程中的
固定右臂关键帧。手指控制、真实物理接触和抓取成功判据保持不变。

最终需要证明：

- Kimodo 和 ARDY 分别通过各自 loader 接入 SONIC。
- 运行时确实使用输入轨迹，不再执行固定右臂关键帧。
- 当前提供的旧 CSV 能完成 integration smoke；不要求抓取今天新建的方块。
- 只有显式绑定当前场景 hash 的抓取专项轨迹才进入抓取正负例验收。
- keyframe 基线没有发生回归。

## 已有基线

- 当前 keyframe 正例：双指接触，抬升约 `95.4 mm`，接触保持约 `4.0 s`。
- 当前 `--no-grip` 负例：零接触、零抬升、`success=False`。
- 方块使用 free joint；场景不使用 weld、adhesion 或位置强制写入。
- 已取得 Kimodo 和 ARDY 的 36 列 qpos CSV 样例。

---

## 阶段 0：冻结抓取基线

### 实现

- 固化当前 keyframe 抓取代码、MuJoCo 场景和运行参数。
- 保存正例与 `--no-grip` 负例的复现命令和结果。
- 在生成轨迹集成完成前保留 keyframe 模式作为回归对照。

### 预期结果

建立一个可重复的抓取基准，后续能区分 motion adapter 问题与原有抓取问题。

### 验收

- 正例 `success=True`。
- `lifted_height >= 0.07 m`。
- `final_clearance >= 0.04 m`。
- `lift_contact_time >= 0.25 s`。
- `max_contact_bodies >= 2`。
- `--no-grip` 必须 `success=False`。
- XML 和运行时代码均不存在 weld、adhesion 或方块位置强制写入。

---

## 阶段 1：定义最终 MotionTrajectory

### 实现

定义统一的数据结构，至少包含：

```python
MotionTrajectory(
    timestamps,       # (T,), seconds
    root_pos,         # (T, 3), world frame
    root_quat_wxyz,   # (T, 4)
    joint_pos,        # (T, 29), canonical IsaacLab order
    joint_vel,        # (T, 29), canonical IsaacLab order
    joint_names,      # 29 unique names
    source_fps,
    source,
    metadata,
)
```

内部关节顺序固定为 IsaacLab 29-DoF，并携带明确关节名，禁止依赖匿名数组猜测顺序。

### 预期结果

Kimodo、ARDY 和后续其他轨迹来源都通过同一个稳定契约进入 SONIC。

### 验收

- 所有逐帧数组的 `T` 一致。
- `timestamps` 严格递增。
- 数组 shape 分别为 `(T, 3)`、`(T, 4)`、`(T, 29)`。
- 所有数值均为有限值。
- 四元数范数有效。
- 29 个关节名完整且唯一。
- 非法 shape、NaN/Inf、重复关节名和非法时间轴必须被拒绝。

---

## 阶段 2：实现 Kimodo 和 ARDY Loader

### 实现

- 实现 `kimodo_loader`。
- 实现 `ardy_loader`。
- 支持无表头 36 列 CSV：
  `root xyz + quaternion wxyz + 29 hinge joints`。
- FPS 必须由命令行或可信元数据显式提供，不能根据帧数猜测。
- 将源文件 SHA-256、帧数、FPS 和 loader 名称写入运行日志。

### 预期结果

两种来源能够独立转换为 `MotionTrajectory`，且加载错误不会静默进入控制链。

### 验收矩阵

| Loader | 输入 | 预期 |
|---|---|---|
| Kimodo | `kimodo_walk_s0.csv` | 读取为 `120 x 36` 并成功转换 |
| Kimodo | pickup/grasp CSV | 按实际帧数读取并成功转换 |
| ARDY | `ardy_final_s0.csv` | 读取为 `100 x 36` 并成功转换 |
| ARDY | `ardy_r5_sha4f_early.csv` | 读取为 `200 x 36` 并成功转换 |

额外验收：

- 转换前后的首帧和末帧逐值一致。
- Kimodo 与 ARDY 日志明确显示使用不同 loader。
- 空文件、错误列数、错误 FPS 和非数值内容必须被拒绝。

---

## 阶段 3：确认骨架和关节契约

### 实现

- 核对源 CSV 的 29 关节名称、顺序和 G1 MuJoCo 模型限位。
- 判断是否需要骨架重定向。
- 只复用现有 `M2I/I2M` 常量，不允许重新定义映射。
- 对轻微数值超限输出关节名、帧号和超限量，再按显式容差裁剪。

### 预期结果

当前样例应被判定为 G1 MuJoCo qpos，不需要骨架重定向，只需要关节顺序转换和限位处理。

### 验收

- MuJoCo -> IsaacLab -> MuJoCo 往返最大误差 `< 1e-6 rad`。
- 映射后每个索引对应正确的关节名称。
- 超限信息可定位到具体文件、帧和关节。
- 不允许静默裁剪明显超限数据。
- 若输入骨架或关节集合不匹配，loader 必须拒绝而不是继续运行。

---

## 阶段 4：坐标转换和重采样

### 实现

- 四元数归一化。
- 修正四元数符号连续性。
- 使用 SLERP 重采样根姿态。
- 对根位置和关节位置做时间插值。
- 归一化初始 heading。
- 将轨迹 root 坐标注册到当前机器人、桌面和方块场景。
- 重采样后按目标时间轴重新计算关节速度。

### 预期结果

不同 FPS 和初始坐标的轨迹能够稳定转换到 SONIC 和当前 MuJoCo 场景使用的统一时间轴与坐标系。

### 验收

- 四元数范数误差 `< 1e-5`。
- 相邻四元数点积非负，避免符号跳变。
- 重采样首尾时刻正确。
- 输出时间戳严格递增。
- 输出无 NaN/Inf 或插值越界。
- 静态轨迹重采样后的关节速度接近零。
- 在原始采样时刻重建时，位置和关节误差满足设定容差。

---

## 阶段 5：生成 SONIC 10 帧 step5 窗口

### 实现

- 在当前参考帧 `t` 生成 `t + [0, 5, ..., 45]` 的未来参考窗口。
- 轨迹尾部采用 hold-last。
- 输出内容：
  - `10 x 29 = 290` 关节速度。
  - `10 x 29 = 290` 绝对关节位置。
  - `10 x 6 = 60` anchor orientation。

### 预期结果

每个 SONIC policy tick 都能获得语义明确、时间推进正确的 640 维参考输入。

### 验收

- 输出总维度严格为 `640`。
- 第一帧、中间帧和末帧窗口索引符合预期。
- 尾部窗口不越界并保持最后有效帧。
- 非静态轨迹至少产生两个不同的窗口 hash。
- 静态站立轨迹与旧静态 encoder adapter 输出一致。

---

## 阶段 6：接入 SonicEncoderAdapter

### 实现

- 将 `SonicEncoderAdapter` 从静态参考改为按时间读取轨迹窗口。
- runner 增加以下参数：

```text
--motion-source
--motion-file
--source-fps
--motion-start
--motion-speed
```

- 每次运行输出 motion 来源、文件 hash、帧数、FPS、当前参考帧范围和窗口 shape。

### 预期结果

SONIC 使用 Kimodo 或 ARDY 轨迹生成的动态参考，而不是固定站立参考。

### 验收

- 每个 policy tick 的 encoder 输入 shape 为 `(640,)`。
- 参考帧索引随仿真时间推进。
- 输入轨迹变化时窗口内容同步变化。
- 无 NaN、维度错误或时间越界。
- 日志能唯一确认实际使用的 loader 和输入文件。

---

## 阶段 7：用生成轨迹替换固定关键帧

### 实现

- generated-motion 模式下禁用 `RIGHT_ARM_*` 固定关键帧覆盖。
- 身体和右臂由 SONIC 的生成轨迹参考驱动。
- 保留独立手指 PD、闭合时序、接触检测和成功判据。
- 保留 keyframe 模式作为回归测试入口。

### 预期结果

机器人动作由输入 CSV 实际决定，同时继续使用现有真实物理抓取和严格成功判据。

### 验收

- generated-motion 模式输出 `fixed_arm_override_count=0`。
- SONIC 参考窗口持续变化。
- 删除、截断或打乱输入轨迹后，运行必须明显变化或被校验拒绝。
- 不允许出现“成功读取 CSV，但仍执行旧关键帧”的假接入。
- keyframe 模式继续通过阶段 0 的正负例。

---

## 阶段 8：端到端验收

阶段 8 分成两层，禁止用 integration smoke 的 `success=False` 推导
loader 或 SONIC 接入失败，也禁止把旧文件名中的 pickup/grasp 当作当前场景
条件已经匹配。

### 测试矩阵

| 测试 | 预期结果 |
|---|---|
| Kimodo walk | loader 和 SONIC 接入成功、窗口推进、无 NaN；不要求抓取成功 |
| ARDY `final_s0` | loader 和 SONIC 接入成功并稳定执行；不要求抓取成功 |
| 旧 Kimodo pickup | loader/SONIC smoke；未绑定当前场景，不要求抓取成功 |
| 旧 ARDY `r5_sha4f_early` | loader/SONIC smoke；未绑定当前场景，不要求抓取成功 |
| 当前 keyframe baseline | 真实物理抓取成功并导出 CSV + manifest |
| 当前 keyframe + `--no-grip` | 必须 `success=False` |
| 新 scene-conditioned Kimodo grasp | 有匹配 manifest 后才要求真实物理抓取成功 |
| 新 scene-conditioned ARDY grasp | 有匹配 manifest 后才要求真实物理抓取成功 |
| 新 scene-conditioned grasp + `--no-grip` | 各来源均必须 `success=False` |

### 抓取成功统一判据

```text
max_contact_bodies >= 2
lifted_height >= 0.07 m
final_clearance >= 0.04 m
lift_contact_time >= 0.25 s
```

### 接入真实性判据

- `fixed_arm_override_count == 0`。
- 日志记录实际输入文件 SHA-256。
- 日志记录 `motion_source`、loader、FPS 和参考帧范围。
- 10 帧 step5 窗口随时间变化。
- 修改输入 CSV 后，参考窗口和机器人动作必须发生对应变化。

### 场景绑定判据

抓取专项轨迹的 manifest 必须记录并匹配：

- CSV、`scene_grasp_hand.xml`、`g1_29dof_with_hand.xml` 的 SHA-256。
- 桌面和方块的位置、尺寸以及右手闭合/抬升时序。
- `scene_conditioned=true`。
- 控制模式是 keyframe ground truth 还是 SONIC closed-loop replay。

当前交付的 baseline 是成功 keyframe 运行记录的 root + 29 body qpos。
手指不在 36 列 CSV 中，由 manifest 固定独立 PD 时序。该资产可作为方法组
生成当前场景动作的参考，但在实测前不声明 SONIC replay 已成功。

## 最终完成定义

### Motion integration 完成

以下条件满足时，Kimodo / ARDY 输入接入算完成：

1. 两个 loader 分别通过格式、错误输入和往返映射测试。
2. 坐标转换、重采样和 640 维窗口测试全部通过。
3. 运行日志证明固定右臂关键帧未参与 generated-motion 模式。
4. Kimodo 和 ARDY 各至少一个 CSV 完成 SONIC smoke，窗口推进且无 NaN。
5. 原 keyframe 抓取基线正例和 `--no-grip` 负例无回归。
6. 基线 CSV、manifest、输入契约、复现命令和自动验收入口齐备。

### Scene-conditioned generated grasp 完成

这是后续独立里程碑。只有 Kimodo 和 ARDY 各自提供绑定当前场景的轨迹，
并分别通过物理正例和 `--no-grip` 负例，才能声明两种方法的生成抓取完成。
旧 CSV 通过 integration smoke 不满足这一声明。
