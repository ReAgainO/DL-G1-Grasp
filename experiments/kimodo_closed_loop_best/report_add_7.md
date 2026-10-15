
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
