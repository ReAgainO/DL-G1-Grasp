## §15 抓取成功率统计 与 自然抓取姿势实验（负结果）

### §15.1 目的与边界
本轮做两件独立的事：
1. **量化 Kimodo 方法的真实抓取成功率**（§15.2–§15.7）——回答"交付的 Kimodo 方法到底
   能成几个"。
2. **尝试把"扭手臂"的抓取姿势换成自然姿势**（§15.8–§15.12）——用户明确要求
   "换成一个自然的抓取姿势，不要像现在这样扭着手臂的动作"。
   结论是**负结果**：在现有 harness 架构下，改 Kimodo 先验与改 `flat_pinch` 约束
   **都无法**降低手腕扭转；扭转是 harness 自身 IK/servo 为达成"指垫水平贴合"
   而涌现出来的，需要改 harness 的目标朝向模型才能消除。

**边界声明**：本增量**未修改** `harness_s1000/`（交付路径）内的任何文件。
`harness_s1000/rep/sonic_grasp.py` 保持 `sha256=0e0435b66da9b9b5d56092246a0deda23c6b38fdac01f7d39e5a8496f14148b9`
不变。所有自然抓取实验在**任务自有的隔离副本** `harness_nat/` 内进行。

### §15.2 成功率实验的受控条件
8 个新单元（扫描 A 抬升 l2–l5、扫描 B 靠近 p2–p5），2026-10-09T07:20:12Z → 07:35:10Z，
全部 `rc=0`，单单元 ~117 s。受控性由**运行器自己写入**的 meta 证明（非命名推断）：
- `sonic_grasp_sha256` 全一致 = `0e0435b6…`
- `runner_sha256` 全一致 = `6f9f44e2b19118b5c040b5d9107400231374d0cf44f43e2d243ce841698555da`
- `.flags_flat` sha 全一致 = `31d3d77548e91ce6deb2f93fff0df4afebb4d5c2d01c107e8080422795559d1a`

**关键方法学**：`run_cell.sh` 把 `motion_stem=` 写进 `raw/<cell>.meta.txt`，
所以 provenance 读的是**运行器写下的真实来源**，不会被目录/文件命名误导。
统计在**片段（clip）级去重**：共享同一片段的多个单元（`wb_dbg_p4`/`wb_dbg2_p4`/
`wb_kimo_p4`/`wb_kimo_v1` 都挂 `p4_conv`）合并为**一次**试验，按最好结局判定。
非 Kimodo 基线（官方 `near_s42`/`reach_s43_v2`）不进分子分母。

### §15.3 片段级成功率（去重后）
| 片段 | 结局 | 抬升高度 m | 失败闸门 |
|---|---|---|---|
| `p1_conv` | FAIL 19/20 | 0.14366 | `no_robot_table_contact_full_task` (3.0108 N) |
| `p2_conv` | **PASS 20/20** | 0.14478 | — |
| `p3_conv` | **PASS 20/20** | 0.14248 | — |
| `p4_conv` | FAIL | — | 靠近时钟溢出 (`Approach clock bound0..26s`) |
| `p5_conv` | FAIL | — | 靠近时钟溢出 |
| `p6_conv` | **PASS 20/20** | 0.14096 | — |

**Kimodo 靠近片段成功率 = 3/6 = 50.0 %**
（已接受 p6 抬升扫描 = 5/6 = 83.3 %，`l3` 因抬升仅 0.10191 m 挂 `hold_7cm`；
官方靠近基线 = 3/4 = 75.0 %）

### §15.4 两种真实失败模式
- **靠近时钟溢出**（p4、p5）：`clearance_approach.py:26` 硬上限 26 s，
  `sonic_grasp.py:300` 的 `approach_timeout=32` **不可达**。p4/p5 幅度过大，
  无法在 26 s 内把腕部抬到 `clearance_z=0.90 m`。调用方看到 `rc=0`
  是因为 traceback 被管道吞掉——必须去 `raw/*.stdout.log` 找崩溃签名。
- **抬升不足**（l3）：`max_lift` 0.10191 m < 0.07 m 门槛以外的余量不足，挂 `hold_7cm`。

### §15.5 幅度与结局的关系
臂链点 15..28 的垂直位移：
通过者 p6 +0.1250、l1 +0.2028、l2 +0.0260、l4 +0.0800、l5 +0.2221；
失败者 p4 +0.1877、p5 +0.1736（**超出靠近窗口**）、l3 −0.0026（**几乎无抬升**）。
**结论：片段必须落在 harness 靠近规划器能接住的幅度窗口内。**

### §15.6 自然抓取实验（新提示词扫描）
新写 6 条**显式要求掌心朝下、肘部自然**的提示词（`probe_reach_nat.sh`，n1–n6），
与官方环境同参（attnfix 补丁生效 `hits=3232`、`fastpath=False`；R2 恢复 Llama-3-8B
llm2vec 预设；`--num_samples 1 --diffusion_steps 100 --seed 42`）。
扭转指标：`elbow_bend`（肘内角，180=直）、`hand_down`（手轴与竖直向下夹角）、
`total_roll`（绕前臂轴的逐帧手滚转积分 = 肉眼所见的"扭"）。

| 片段 | total_roll | hand_down | 判断 |
|---|---|---|---|
| 旧 `p6_conv` | 118.30° | 125.47° | 交付基线 |
| 官方 `near_s42` | 79.66° | — | 官方基线 |
| **`n2`** | **64.93°** | — | 最佳，但**OOD 下蹲**（root_z 0.4450–0.4524）→ 弃用 |
| `n4` | 89.06° | — | root_z 0.7745–0.7767 **正常站立** → 选用 |
| n1/n3/n5/n6 | 258–469° | — | 弃用 |

`n4` 通过完整 20 闸门：`wb_nat_n4l1` **success=True，20/20，抬升 0.14129 m**，
CSV 已导出（1789 行 = 表头 + 1788，1054030 B，51 列，相位 SETTLE→SETTLE_RELEASE，59.56 s）。

### §15.7 决定性负结果：换提示词**改变不了**最终动作
对比 `n4` 与交付基线的**最终仿真轨迹**：
`total_roll` **307.19° → 315.66°（+2.8 %，反而更扭）**，`hand_down` 27.24 → 27.05，
`elbow` 84.44 → 84.91。按相位拆解各相位差 ≤7°，`hand_down` 几乎不变。
**结论：Kimodo 先验对最终手腕姿态无控制权。**

### §15.8 根因定位（决定性）
`sonic_grasp.py` 中 `ik()` 是**模块级函数**（非 `run()` 的嵌套闭包），
`pinch_geometry` 分支（我们走的那条）第 **240** 行：
```python
close_hand[2]=-.88;grasp=initial_cube.copy();highpos=grasp+np.array([0,0,.10])
lowR=d.xmat[wrist].reshape(3,3).copy();highR=lowR.copy()
```
**`lowR` 与 `highR` 都取自 rollout t=0 的 `d.xmat[wrist]`——机器人初始腕姿。**
随后第 318/320 行做 `rotation_blend(route_start_R, highR, u)`。
即：**片段的腕部旋转在整个靠近与抓取过程中都被结构性排除在外。**
第 222 行的 `native_R[native_frame]` 路径只在 `--native-geometry` 下生效，我们未启用。
另外两个片段在 `native_frame` 的腕旋转只差 **11.15°**，换片段本就不可能解决问题。

### §15.9 `--flat-pinch-relax` 补丁实验（证伪 `flat_pinch` 假设）
原假设：`--flat-pinch` 强制三个指垫高度差→0（指垫共面 = 手掌水平），
而手掌水平必须靠手腕大幅 roll 达成，所以"扭"是 `flat_pinch` 强制的。
为此在**隔离副本** `harness_nat/` 上加 `--flat-pinch-relax K`（缩放共面性两行，
`K=1.0` 应与原版逐位等价）。5 个单元，全部 `rc=0`：

| K | success | gates | max_lift m | total_roll | hand_down | elbow |
|---|---|---|---|---|---|---|
| 1.0（对照） | ✅ | 20/20 | 0.14399 | 344.70° | 27.24° | 84.44° |
| 0.6 | ✅ | 20/20 | 0.13876 | 343.07° | 27.22° | 84.52° |
| **0.4** | ✅ | 20/20 | 0.14008 | **332.13°** | 26.86° | 84.51° |
| 0.2 | ✅ | 20/20 | 0.13953 | 346.50° | 27.28° | 84.45° |
| 0.0 | ❌ | 9/20 | — | 99.19° | 48.26° | 101.58° |

**两条结论**：
1. **放宽共面性约束并不降低扭转**：K=1.0→0.2 之间 `total_roll` 只在 14° 噪声带内
   摆动（344.7/343.1/332.1/346.5），`hand_down` 钉在 27.2±0.2°、`elbow` 84.4±0.1°。
   即 `flat_pinch` **不是**扭转的约束来源——原假设**被证伪**。
2. **K=0.0 直接做不成任务**（47 s 就结束，20 闸门里挂 11 个：`completed`、
   `hold_7cm`、`two_fingers`、`no_support`、`clearance_4cm`、`slip_1cm`、
   `release_drop_6cm` …）。所以该约束是**承重的**，只是不负责扭转。

**对照有效性证明**：`K=1.0` 单元与交付基线 `wb_kimo_p6l1` 的**逐相位扭转完全一致**
（SETTLE 25.4 / APPROACH 193.1 / PREGRASP 42.3 / DESCEND 29.7 / ALIGN 0.1 /
CLOSE 3.2 / LIFT 38.4 / HOLD 4.5 / RELEASE 2.7 / SETTLE_RELEASE 5.2，
TOTAL 344.7）→ 补丁在 K=1.0 是**真无操作**，比较成立。

### §15.10 扭转的相位来源
56.0 % 的扭转发生在 **APPROACH**（193.1°/344.7°），其次 PREGRASP 12.3 %、
LIFT 11.1 %、DESCEND 8.6 %、SETTLE 7.4 %。
APPROACH 正是由 `quint(e/10)` 在 `route_start_pos → highpos` 间固定插值、
朝向锁在 `highR` 的相位。**扭转是 harness 靠近插值 + 腕目标种子的产物。**

### §15.11 结论与所需方向
**"换成自然抓取姿势"不能在现有架构下通过改先验或改约束达成。**
要真正消除扭转，必须改 harness 的**抓取目标朝向模型**，至少二选一：
- 启用 `--native-geometry`，让片段的 `native_R[native_frame]` 进入 `lowR`/`highR`；
- 或给 IK 增加显式的**腕自然度目标**（把腕 roll 作为软代价而非靠共面性间接约束）。
后者需要重跑全部闸门回归，属于**架构级改动**，不在本增量授权范围内。

### §15.12 资源纪律
`/home` 仍接近满（见 §14.7），本增量**只写 `/data`**；
`harness_nat/` 为 524 MB 隔离副本（`cp -a`）；`TMPDIR`/`XDG_CACHE_HOME` 显式钉在 `/data`；
所有 cell `nice -n 19`，`timeout 1500`。`/data` 扫描时 11 TiB 可用，远高于 30 GiB 红线。

### §15.13 遗留
- 官方 keyframe 基线仅在 MuJoCo 3.2.7 下可复现（版本差异需 SONIC 侧确认）。
- `repos/kimodo` 仍带着别的任务未提交的 Mistral 文本编码器预设改动，
  干净修法是回滚，需仓库属主决策。
- harness 潜在缺陷：`sonic_grasp.py:300 approach_timeout=32` 因
  `clearance_approach.py:26` 的 26 s 上限而**不可达**。
- `harness_nat/` 下的 `wb_nat_r*` 与 `wb_nat_n4l1` 为实验证据，保留备查。
