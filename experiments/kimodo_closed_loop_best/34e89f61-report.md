# SONIC 环境仿真 → 视频渲染报告

**任务** `20261008-232029-workbuddy-34e89f61` ｜ **节点** `group4@10.123.0.39`
**增量** 把已验证的 SONIC harness 抓取轨迹渲染成 H.264 视频
**时间** 2026-10-09 02:45 – 03:05 (+08:00)

---

## 1. 一句话结论

用**节点上既有的** MuJoCo 场景/状态 + OSMesa + `envs/render` 里自带的静态 ffmpeg 7.0.2，
把 SONIC harness 的 `wb_kimo_p6l1` run **逐帧（不抽帧）** 渲染并编码成 4 支 MP4，
真实速率 25 fps、960×720。视频完整呈现 **右臂靠近 → 腕部对齐 → 手指闭合 → 抬升 → 保持 → 放回**，
抬升峰值 **+152.7 mm**，抓取期间右手指与方块接触数持续为 **2**。

**没有新建任何环境**：模型、相机、状态全部来自 SONIC 侧已经落盘的 run 目录。

---

## 2. 渲染链路（每一环都可复核）

```
SONIC harness run (已落盘，只读)
  /data/group4/<TID>/harness_s1000/rep/out/wb_kimo_p6l1/
      scene.xml            场景（含 g1_free_grasp.xml）
      g1_free_grasp.xml    机器人模型（绝对 meshdir）
      trajectory.npz       qpos(1490,57) / phase / time / fps=25
              │
              ▼  wb_render_video.py   （逐帧回放，MuJoCo 自带的 mj_forward + Renderer）
      video_frames/main/f%05d.jpg    1490 帧  机位 = SONIC 场景自带的 grasp_camera
      video_frames/side/f%05d.jpg    1490 帧  机位 = 跟踪方块的近景
              │
              ▼  ffmpeg 7.0.2-static（节点既有，libx264）
      *.mp4  H.264 High / yuv420p / CRF 18 / +faststart
```

| 环节 | 用了什么 | 是否新装 |
| --- | --- | --- |
| 动力学状态 | SONIC harness 的 `trajectory.npz` | 否（既有） |
| MuJoCo 模型与相机 | SONIC harness 的 `scene.xml` / `g1_free_grasp.xml` | 否（既有） |
| 离屏渲染 | `MUJOCO_GL=osmesa` + `render_test/mesa_probe` 的 `libOSMesa` | 否（既有） |
| 视频编码 | `envs/render/.../imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2` | 否（既有） |

> 本节点**没有系统级 ffmpeg**（`ffmpeg: command not found`）。可用的是
> `imageio_ffmpeg` 自带的 79 MB 静态件，实测 `-version` 为
> `ffmpeg version 7.0.2-static`，配置含 `--enable-libx264`。该 env 属他人任务，
> 本增量**只读执行、未写入**。

---

## 3. 交付视频

| 文件 | 内容 | 时长 | 体积 | sha256 |
| --- | --- | --- | --- | --- |
| `g1-rightcube-sim-grasp-full.mp4` | 全程，SONIC 场景自带 `grasp_camera` 视角 | 59.60 s | 5.77 MB | `1c51a0c8f0264dd0…` |
| `g1-rightcube-sim-grasp-closeup.mp4` | 全程，跟踪方块的近景 | 59.60 s | 9.50 MB | `a34a4b451b18a3e2…` |
| `g1-rightcube-sim-grasp-decisive.mp4` | 决定性窗口 t=43.2–56.8 s，近景 | 13.64 s | 3.32 MB | `2943a24c0d3f503a…` |
| `g1-rightcube-sim-grasp-decisive-wide.mp4` | 同一窗口，宽视角 | 13.64 s | 1.48 MB | `7fc81927a9500fc7…` |

全部：`h264 (High), yuv420p, 960x720, 25 fps, SAR 1:1`。
全长视频是 **stride 1 逐帧**（1490 帧 ÷ 25 fps = 59.60 s），**不是抽帧加速**。

每帧左上角有 HUD，便于逐帧对账：
`t=… s  frame i/1489` / `phase=…  cube_z=… m  rise=… mm  right-hand/cube contacts=n`，
抓稳后追加一行 `>>> GRASPED: …`。

---

## 4. 视频中的关键读数

| t (s) | 相位 | cube_z (m) | rise (mm) | 右手指/方块接触 |
| --- | --- | --- | --- | --- |
| 43.22 | DESCEND | 0.7744 | −0.1 | 0 |
| 44.90 | CLOSE | 0.7744 | −0.1 | 0 |
| 46.58 | LIFT | 0.8258 | **+51.4** | **2** |
| 48.26 | LIFT | 0.8660 | +91.7 | 2 |
| 49.94 | LIFT | 0.9098 | +135.4 | 2 |
| 51.62 | LIFT | 0.9172 | +142.7 | 2 |
| 53.28 | LIFT | 0.9267 | **+152.2** | 2 |
| 54.96 | HOLD | 0.9189 | +152.7 | **2** |
| 56.64 | SETTLE_RELEASE | 0.7744 | −0.1 | 0 |

（`rise` 以第一帧 `cube_z = 0.7744 m` 为基准；读数来自 `trajectory.npz` 与逐帧前向运动学。）

---

## 5. 复现

```bash
T=20261008-232029-workbuddy-34e89f61
B=/home/group4/group4_dasc7606c

# 全量渲染 + 编码（约 14 分钟，1490 帧 × 双机位）
setsid nohup nice -n 19 bash $B/work/$T/workbuddy/scripts/wb_render_video_run.sh \
  > /data/group4/$T/sonic_bridge_replay/video.log 2>&1 < /dev/null &

# 决定性窗口短片
bash $B/work/$T/workbuddy/scripts/wb_video_decisive.sh

# 从 mp4 抽帧做联系表（免下载即可核对）
bash $B/work/$T/workbuddy/scripts/wb_video_contact.sh
```

中间帧序列保留在 `/data/group4/<TID>/sonic_bridge_replay/video_frames/{main,side}/`，
各 1490 帧，合计 328 MB，可随时按不同参数重编码而不必重渲。

---

## 6. 已知边界与遗留

1. **`/home` 仅剩 4.3 GiB（98% 占用）**，低于 AGENTS.md §6 的 30 GiB 红线。
   本增量全程只写 `/data`（11 TiB 可用），并显式 `TMPDIR=/data/group4/<TID>/tmp`。
   若后续还要在 `/home` 落盘，须先与账号主人确认。
2. 本次渲染的是 **SONIC harness 路径**（20/20 门全绿）的轨迹，不是官方桥接
   `run_grasp.py` 的轨迹——后者在本节点因 MuJoCo 3.14.0 / harness 3.2.7 版本差而物理失败，
   详见 `reports/<TID>-report.md` 上一版（§13）。
3. 视频无音轨（无需）；若需 GIF 版本，见 `wb_deliverable/g1-rightcube-sim-motion*.gif`。


---

## 7. 抓取成功率统计 与 自然抓取姿势实验（负结果）

> 本节对应账本 `logs/20261008-232029-workbuddy-34e89f61/steps.md` 的 §15（§15.1–§15.13），
> 数据文件 `/data/group4/20261008-232029-workbuddy-34e89f61/nat_sweep.json`
> 与 `kimodo_success_rate.json`。

### 7.1 Kimodo 方法的真实抓取成功率

方法学（两条硬约束，避免自欺）：
- **provenance 读运行器写下的真值**：`run_cell.sh` 把 `motion_stem=` 写进
  `raw/<cell>.meta.txt`，统计脚本读这个字段，**不靠目录/文件名推断**。
- **片段级去重**：共享同一片段的多个单元合并为**一次**试验，按最好结局判定。
  例如 `wb_dbg_p4`/`wb_dbg2_p4`/`wb_kimo_p4`/`wb_kimo_v1` 都挂 `p4_conv` → 只算 1 次。
  非 Kimodo 基线（官方 `near_s42`、`reach_s43_v2`）不进分子分母。

受控性由运行器自写 meta 证明（8 个新单元，2026-10-09T07:20:12Z → 07:35:10Z，
全部 `rc=0`，单单元 ~117 s）：`sonic_grasp_sha256`、`runner_sha256`、
`.flags_flat` sha 三者**全一致**，只有 `name` 与被换的片段不同。

| 片段 | 结局 | 抬升高度 m | 失败闸门 |
|---|---|---|---|
| `p1_conv` | FAIL 19/20 | 0.14366 | `no_robot_table_contact_full_task`（3.0108 N） |
| `p2_conv` | **PASS 20/20** | 0.14478 | — |
| `p3_conv` | **PASS 20/20** | 0.14248 | — |
| `p4_conv` | FAIL | — | 靠近时钟溢出（`Approach clock bound0..26s`） |
| `p5_conv` | FAIL | — | 靠近时钟溢出 |
| `p6_conv` | **PASS 20/20** | 0.14096 | — |

> **Kimodo 靠近片段成功率 = 3/6 = 50.0 %**

对照组：已接受 p6 的**抬升扫描 = 5/6 = 83.3 %**（`l3` 抬升仅 0.10191 m，挂 `hold_7cm`）；
官方靠近基线 = 3/4 = 75.0 %。

**两种真实失败模式**（都不是"没跑"，而是真的失败）：
- **靠近时钟溢出**（p4/p5）：`clearance_approach.py:26` 硬上限 26 s，
  `sonic_grasp.py:300 approach_timeout=32` 不可达。幅度过大者无法在 26 s 内
  把腕部抬到 `clearance_z=0.90 m`。**注意**：调用方看到 `rc=0`，因为 traceback 被管道
  吞掉——必须去 `raw/*.stdout.log` 找崩溃签名，否则会误判成"没跑"。
- **抬升不足**（l3）：0.10191 m，余量低于门槛，挂 `hold_7cm`。

**幅度窗口结论**：臂链点 15..28 的垂直位移——通过者 p6 +0.1250、l1 +0.2028、
l2 +0.0260、l4 +0.0800、l5 +0.2221；失败者 p4 +0.1877、p5 +0.1736（**超出靠近窗口**）、
l3 −0.0026（**几乎无抬升**）。**片段必须落在 harness 靠近规划器能接住的幅度窗口内。**

### 7.2 自然抓取姿势实验：为什么改不动

用户要求"换成一个自然的抓取姿势，不要像现在这样扭着手臂的动作"。
我们做了**两条独立路线**，都是**负结果**。

**路线 A — 换 Kimodo 提示词。** 新写 6 条显式要求"掌心朝下、肘部自然"的提示词
（n1–n6），官方环境同参（attnfix 补丁生效 `hits=3232`、`fastpath=False`；
恢复 Llama-3-8B llm2vec 预设；seed 42）。

| 片段 | total_roll（越小越自然） | 判断 |
|---|---|---|
| 交付基线 `p6_conv` | 118.30° | — |
| 官方 `near_s42` | 79.66° | 官方基线 |
| **`n2`** | **64.93°**（最佳） | 但 **OOD 下蹲**（root_z 0.4450–0.4524）→ 弃用 |
| `n4` | 89.06° | root_z 0.7745–0.7767 **正常站立** → 选用 |
| n1/n3/n5/n6 | 258–469° | 弃用 |

`n4` 通过完整 20 闸门（`wb_nat_n4l1`，success=True，抬升 0.14129 m）。
但对比**最终仿真轨迹**：`total_roll` **307.19° → 315.66°（+2.8 %，反而更扭）**，
`hand_down` 27.24 → 27.05，`elbow` 84.44 → 84.91，逐相位差 ≤7°。
**换提示词改变不了最终手腕姿态。**

**路线 B — 放宽 `flat_pinch` 约束。** 原假设：`--flat-pinch` 强制三指垫共面
（手掌水平），而手掌水平必须靠手腕大幅 roll 达成——所以"扭"是被该约束强制的。
为此在**隔离副本** `harness_nat/`（交付路径 `harness_s1000/` 未动，
`sonic_grasp.py` sha 保持 `0e0435b6…`）加 `--flat-pinch-relax K`（缩放共面性两行，
`K=1.0` 应与原版逐位等价）。5 个单元全部 `rc=0`：

| K | success | gates | max_lift m | total_roll | hand_down | elbow |
|---|---|---|---|---|---|---|
| 1.0（对照） | ✅ | 20/20 | 0.14399 | 344.70° | 27.24° | 84.44° |
| 0.6 | ✅ | 20/20 | 0.13876 | 343.07° | 27.22° | 84.52° |
| **0.4** | ✅ | 20/20 | 0.14008 | **332.13°** | 26.86° | 84.51° |
| 0.2 | ✅ | 20/20 | 0.13953 | 346.50° | 27.28° | 84.45° |
| 0.0 | ❌ | 9/20 | — | 99.19° | 48.26° | 101.58° |

- **放宽约束并不降低扭转**：K=1.0→0.2 之间 `total_roll` 只在 14° 噪声带内摆动，
  `hand_down` 钉在 27.2±0.2°、`elbow` 84.4±0.1°。**`flat_pinch` 不是扭转的来源，
  原假设被证伪。**
- **K=0.0 直接做不成任务**：47 s 就结束，20 闸门挂 11 个（`completed`、`hold_7cm`、
  `two_fingers`、`no_support`、`clearance_4cm`、`slip_1cm`、`release_drop_6cm` …）。
  该约束**是承重的**，只是不负责扭转。
- **对照有效性**：`K=1.0` 与交付基线 `wb_kimo_p6l1` 的**逐相位扭转完全一致**
  （SETTLE 25.4 / APPROACH 193.1 / PREGRASP 42.3 / DESCEND 29.7 / ALIGN 0.1 /
  CLOSE 3.2 / LIFT 38.4 / HOLD 4.5 / RELEASE 2.7 / SETTLE_RELEASE 5.2，TOTAL 344.7），
  证明补丁在 K=1.0 是**真无操作**，比较成立。

### 7.3 根因（决定性）

`sonic_grasp.py` 的 `ik()` 是**模块级函数**（非 `run()` 的嵌套闭包）。
`pinch_geometry` 分支（我们走的那条）第 **240** 行：

```python
close_hand[2]=-.88;grasp=initial_cube.copy();highpos=grasp+np.array([0,0,.10])
lowR=d.xmat[wrist].reshape(3,3).copy();highR=lowR.copy()
```

**`lowR` 与 `highR` 都取自 rollout t=0 的 `d.xmat[wrist]`——机器人初始腕姿。**
随后第 318/320 行做 `rotation_blend(route_start_R, highR, u)`。
即：**片段的腕部旋转在整个靠近与抓取过程中都被结构性排除在外。**
第 222 行的 `native_R[native_frame]` 路径只在 `--native-geometry` 下生效（我们未启用）；
且两个片段在 `native_frame` 的腕旋转只差 **11.15°**——换片段本就不可能解决问题。

扭转的相位分布证实了这一点：**56.0 % 的扭转发生在 APPROACH**
（193.1°/344.7°），而 APPROACH 正是由 `quint(e/10)` 在
`route_start_pos → highpos` 间固定插值、朝向锁死在 `highR` 的相位。

### 7.4 结论

**"换成自然抓取姿势"在现有 harness 架构下，无法通过改 Kimodo 先验或改 `flat_pinch`
约束达成。** 扭转是 harness 自身 IK/servo 为达成"指垫水平贴合"而**涌现**的属性。
要真正消除，必须改 harness 的**抓取目标朝向模型**，至少二选一：

- 启用 `--native-geometry`，让片段的 `native_R[native_frame]` 进入 `lowR`/`highR`；
- 或给 IK 增加**显式的腕自然度目标**（把腕 roll 作为软代价，而非靠共面性间接约束）。

后者需重跑全部闸门回归，属**架构级改动**，未在本增量授权范围内，需用户明确确认。

### 7.5 交付物索引（本增量）

| 文件 | 说明 |
|---|---|
| `nat_sweep.json` | 5 个 `--flat-pinch-relax` 单元的闸门 + 扭转指标 |
| `kimodo_success_rate.json` | 片段级去重成功率 |
| `ledger_add_15.md` | 账本 §15 增量（已追加至 `steps.md`，531 行） |
| `harness_nat/` | 隔离实验副本（524 MB）；`wb_nat_r*`、`wb_nat_n4l1` 为证据 |
| `quarantine_nat_rc1/` | 首次失败的 5 个单元（`NameError`），保留备查 |
| `nat_sweep.log` / `robust_sweep.log` | 扫描日志 |

**隔离声明**：`harness_s1000/`（交付路径）**全程未被修改**，
`rep/sonic_grasp.py` sha256 仍为
`0e0435b66da9b9b5d56092246a0deda23c6b38fdac01f7d39e5a8496f14148b9`。


---

## 8. 再次尝试自然姿态抓取（不改交付版本）：朝向通道被证明是死代码

> 对应账本 §16（§16.0–§16.9）。前提：用户明确要求
> **"一定不能够修改任何之前成功的那一版内容"**。

### 8.1 交付版本零改动（已实测验证）

| 检查项 | 结果 |
|---|---|
| `harness_s1000/rep/sonic_grasp.py` sha256 | `0e0435b6…148b9` —— **与交付时一致** |
| 该文件 mtime | `2026-10-08 06:31:21 +0800` —— **早于本轮全部工作** |
| 交付闭环单元 `wb_kimo_p6l1` | 仍 `success=True`，**20/20** |
| 交付 CSV sha256 | `709fd544…9eefd` —— **未变** |

全部新实验在隔离副本 `harness_nat/` 内完成。

### 8.2 本轮思路

§15 已证伪"改提示词"和"放宽 `flat_pinch`"。本轮攻 §15 指出的另一条路：
**让 Kimodo 片段的腕姿态进入抓取朝向**。harness 自带 `--native-geometry`
（第 223–227 行），注释明写 *"Keep the generated near-reach wrist orientation
rather than human large wrist rotations"* —— 正是"自然姿态"所需机制。

但它与我们的 flag 集冲突：第 249/261 行断言 `clearance_approach`/`kinematic_servo`
**必须** `pinch_geometry`，而第 240 行（`pinch_geometry` 分支）会把
`lowR`/`highR` **覆盖**回 t=0 腕姿。故在隔离副本加 `--pinch-native-orientation`
（+ SLERP 混合 `--pinch-native-blend`），让 `pinch_geometry` 下也能取片段朝向。

### 8.3 实验一：直接取片段朝向 → 失败

| 单元 | 片段 | 朝向 | 结果 |
|---|---|---|---|
| `wb_nat2_p6_off` | p6_conv | off | **rc=0**，20/20，lift 0.14399 |
| `wb_nat2_p6_on` | p6_conv | on | **rc=1**，`Approach clock bound0..26s` |
| `wb_nat2_n4_off` | n4_conv | off | **rc=0**，20/20，lift 0.14129 |
| `wb_nat2_n4_on` | n4_conv | on | **rc=1**，同上 |

两个对照**逐位复现**交付基线（p6 `max_ik_position_error_m` = 0.241967，
与 `wb_kimo_p6l1` 完全一致）。

### 8.4 几何诊断：旋转在位置计算中代数抵消

实测（`p6_conv`，`native_frame=49`）：
- t=0 腕姿与 `native_R[49]` 的**测地差 = 81.44°**（差异确实很大）
- 但两种朝向算出的 `grasp`/`highpos` **完全相同**（`highpos_z=1.0102`）

原因：`grasp = initial_cube + lowR@(lowR.T@offset)`，而旋转矩阵恒满足
`R@(R.T@v) = v`（对**任意** R 成立，数值验证误差 6.7e-16）。
⇒ **`grasp`/`highpos` 与 `lowR` 无关；朝向只影响 `targetR`。**

### 8.5 实验二：SLERP 混合扫描 → 全部通过，但逐位无变化

| blend | gates | max_lift | total_roll | hand_down | elbow |
|---|---|---|---|---|---|
| 0.0 / 0.1 / 0.2 / 0.35 / 0.5 / 0.75 / 1.0 | 全部 **20/20** | 全部 **0.14399** | 全部 **344.70°** | 全部 **27.24°** | 全部 **84.44°** |

**七行完全逐位相同。** 把被指令的腕朝向从 t=0 一路换到片段姿态（跨 81°），
最终执行出的动作**一个比特都没变**。这比 §15 的结论更强。

### 8.6 根因（决定性，一次解释全部三次负结果）

`sonic_grasp.py:397`：
```python
goal=(last_goal.copy() if policy_aware or kinematic_servo or discrete_servo
      else ik(...,targetR,...)) if phase!='SETTLE' else neutral[arm].copy()
```
我们的 flag 集含 **`--kinematic-servo`** ⇒ 条件为真 ⇒ **`goal=last_goal.copy()`，
带 `targetR` 的那次 `ik(...)` 根本不执行。`targetR` 是死代码。**

`sonic_grasp.py:400`：`--clearance-native-branch` 下 APPROACH 目标由
**`native_branch_target`** 接管，再次覆盖 IK。

`native_branch.py:192` 调用 IK 时逐参数映射（已核对签名）：
| 形参 | 实参 | 含义 |
|---|---|---|
| `R` | **`np.eye(3)`** | 单位阵占位，**朝向目标被显式丢弃** |
| `weight` | **`0.`** | 冗余先验项禁用 |
| `pinch`/`flat_pinch`/`surface` | `True` | 朝向仅由**指垫共面行**间接约束 |

⇒ servo 分支里**唯一**能影响腕朝向的机制就是 `flat_pinch` 的共面约束 ——
而 §15.9 已实测：放宽它不改变扭转，去掉它直接失败。

**统一结论：`lowR`/`highR`/`targetR` 这条朝向通道整套是死代码。**
它同时解释了 §15.7（换提示词无效）、§15.9（放宽 flat_pinch 无效）、
§8.5（跨 81° 换朝向比特级无变化）。

### 8.7 结论

**在"不改交付版本"的约束下，用 Kimodo 方法无法达成自然姿态抓取。**
原因不是先验、不是提示词、不是约束强度，而是 **harness 的 `kinematic_servo`
架构根本不消费朝向指令**。要真正改变腕姿态，必须改 `sonic_grasp.py:397/400`
的 control-flow，属**架构级改动**，与"不能修改成功版本"直接冲突。

**因此本轮不产出新的交付 CSV；交付仍是 `wb_kimo_p6l1` 那一版。**

### 8.8 若放宽约束，最小可行改法（备选，未执行）

1. 在 `sonic_grasp.py:397` 前插入：当启用片段朝向时，用带 `targetR` 的 IK
   修正 `goal`（而非 `last_goal`）；
2. 或在 `native_branch.py` 候选评分中加入**腕自然度项**（当前仅
   `capture_error`/`pad_spread`/`limit_margin`/`clearance`/`finger_error`/
   `native_pose_deviation`），把 roll 作为软代价。

任一项都需重跑 20 闸门回归，且**必须改交付 harness** —— 需用户明确授权。
