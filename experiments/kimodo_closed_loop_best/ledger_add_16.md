## §16 再次尝试自然姿态抓取：orientation 通道被证明是死代码（决定性）

### §16.0 前提承诺与验证
用户要求：**"一定不能够修改任何之前成功的那一版内容"**，在此前提下再次用 Kimodo
方法尝试自然姿态抓取。

**交付版本零改动证明**（本轮结束后实测）：
- `harness_s1000/rep/sonic_grasp.py` sha256 = `0e0435b66da9b9b5d56092246a0deda23c6b38fdac01f7d39e5a8496f14148b9`（**与交付时一致**）
- 该文件 mtime = `2026-10-08 06:31:21 +0800`（**早于本轮全部工作**，未被写过）
- 交付闭环单元 `wb_kimo_p6l1` 仍 `success=True`，20/20
- 交付 CSV `wb_deliverable/g1-rightcube-grasp-kimodo-30fps.csv` sha256 = `709fd544ce68c28feb57a2d8e61831824d9fc4254c70375c297254bf09b9eefd`（未变）

全部新实验在**任务自有的隔离副本** `harness_nat/` 内进行。

### §16.1 本轮假设与实验设计
§15 已证伪"改提示词"与"放宽 `flat_pinch`"。本轮针对 §15.11 提出的第一条方向：
**让 Kimodo 片段的腕姿态进入抓取朝向**（`lowR`/`highR`）。

先发现 harness **自带** `--native-geometry`（第 223–227 行），其注释明写
*"Keep the generated near-reach wrist orientation rather than human large wrist
rotations"*——正是"自然姿态"想要的机制。但第 249/261 行断言
`clearance_approach`/`kinematic_servo` **必须** `pinch_geometry`，
而第 240 行（`pinch_geometry` 分支）会把 `lowR`/`highR` **覆盖**回 t=0 腕姿。
两者不可同时生效，故在隔离副本中加 `--pinch-native-orientation`，
使 `pinch_geometry` 下也能取片段朝向（并加 SLERP 混合 `--pinch-native-blend`）。

### §16.2 实验一：直接取片段朝向 → 失败
矩阵（`wb_nat2_*`，仅朝向不同，其余受控）：

| 单元 | 片段 | 朝向 | 结果 |
|---|---|---|---|
| `wb_nat2_p6_off` | p6_conv | off | **rc=0**，20/20，lift 0.14399 |
| `wb_nat2_p6_on` | p6_conv | on | **rc=1** — `Approach clock bound0..26s` |
| `wb_nat2_n4_off` | n4_conv | off | **rc=0**，20/20，lift 0.14129 |
| `wb_nat2_n4_on` | n4_conv | on | **rc=1** — 同上 |

两个对照**逐位复现**交付基线（p6 的 `max_ik_position_error_m` = 0.241967，
与 `wb_kimo_p6l1` 完全一致）。

### §16.3 几何诊断：旋转在位置计算中代数抵消
`wb_nat2_geom.py` 实测（`p6_conv`，`native_frame=49`）：
- t=0 腕姿与 `native_R[49]` 的**测地差 = 81.44°**（确实很大）
- 但两种朝向算出的 `grasp` / `highpos` **完全相同**（`highpos_z=1.0102`）

原因：`grasp = initial_cube + lowR@(lowR.T@offset)`，而旋转矩阵满足
`R@(R.T@v) = v`（对**任意** R 成立，已数值验证，误差 6.7e-16）。
⇒ **`grasp`/`highpos` 与 `lowR` 无关；朝向只影响 `targetR`（被指令的腕旋转）。**

### §16.4 实验二：SLERP 混合扫描 → 全部通过但全部无效
用 `_slerp`（体积正确、端点精确，已单元测试）从 t=0 朝向向片段朝向混合，
扫 `blend = 0.0/0.1/0.2/0.35/0.5/0.75/1.0`（`wb_nat3_p6_*`）：

| blend | success | gates | max_lift | total_roll | hand_down | elbow |
|---|---|---|---|---|---|---|
| 0.0 | ✅ | 20/20 | 0.14399 | 344.70° | 27.24° | 84.44° |
| 0.1 | ✅ | 20/20 | 0.14399 | 344.70° | 27.24° | 84.44° |
| 0.2 | ✅ | 20/20 | 0.14399 | 344.70° | 27.24° | 84.44° |
| 0.35 | ✅ | 20/20 | 0.14399 | 344.70° | 27.24° | 84.44° |
| 0.5 | ✅ | 20/20 | 0.14399 | 344.70° | 27.24° | 84.44° |
| 0.75 | ✅ | 20/20 | 0.14399 | 344.70° | 27.24° | 84.44° |
| 1.0 | ✅ | 20/20 | 0.14399 | 344.70° | 27.24° | 84.44° |

**七行全部逐位相同**（roll/hand_down/elbow/lift 完全一致）。
即：**把被指令的腕朝向从 t=0 一路换到片段姿态（跨 81°），最终执行出的动作
一个比特都没变。** 这比 §15 的结论更强。

### §16.5 根因（决定性，一次解释全部三次负结果）
`sonic_grasp.py:397`：
```python
goal=(last_goal.copy() if policy_aware or kinematic_servo or discrete_servo
      else ik(...,targetR,...)) if phase!='SETTLE' else neutral[arm].copy()
```
我们的 flag 集含 **`--kinematic-servo`** ⇒ 条件为真 ⇒ **`goal=last_goal.copy()`，
带 `targetR` 的那次 `ik(...)` 调用根本不执行。** `targetR` 是**死代码**。

`sonic_grasp.py:400`：`--clearance-native-branch` 下 APPROACH 的目标由
**`native_branch_target`** 接管，再次覆盖 IK 结果。

`native_branch.py:192`（`select_native_branch` 内）调用 IK 时：
```python
ik_function(m,f,arm_qadr,arm_vadr,np.asarray(tgt),np.eye(3),q,seed,0.,True,True,True,cube_R,opponent)
```
逐参数映射（已核对签名）：
| 形参 | 实参 |
|---|---|
| `R` | **`np.eye(3)`**（单位阵占位，朝向目标被显式丢弃） |
| `prior` | `seed` |
| `weight` | **`0.`**（冗余先验项禁用） |
| `pinch` / `flat_pinch` / `surface` | `True`/`True`/`True` |

⇒ 在 servo 分支里，**唯一**能影响腕朝向的机制是 `flat_pinch` 的**指垫共面行**——
而这正是 §15.9 已实测"放宽它不改变扭转、去掉它直接失败"的那一项。

**统一结论：`lowR`/`highR`/`targetR` 这条朝向通道整套都是死代码。**
它解释了 §15.7（换提示词无效）、§15.9（放宽 flat_pinch 无效，只影响成败不影响扭转）、
§16.4（跨 81° 换朝向比特级无变化）。

### §16.6 结论
**在"不改交付版本"的约束下，用 Kimodo 方法无法达成自然姿态抓取**，原因是
**不是先验问题、不是提示词问题、不是约束强度问题，而是 harness 的
`kinematic_servo` 架构根本不消费朝向指令**。要真正改变腕姿态，必须改
`sonic_grasp.py` 第 397/400 行的 control-flow（让 `targetR` 真正参与），
这属于**交付 harness 的架构级改动**，与用户"不能修改成功版本"的约束直接冲突。

**因此本轮不产出新的交付 CSV**——交付仍是 `wb_kimo_p6l1` 那一版。

### §16.7 若用户愿意放宽约束，最小可行改法（备选，未执行）
1. 在 `sonic_grasp.py:397` 之前插入：当 `PINCH_NATIVE_ORIENTATION` 时，
   把 `goal` 用一次带 `targetR` 的 IK 修正（而非 `last_goal`）；
2. 或在 `native_branch.py` 的候选评分中加入**腕自然度项**（当前只有
   `capture_error`/`pad_spread`/`limit_margin`/`clearance`/`finger_error`/
   `native_pose_deviation`），把 roll 作为软代价。
任一项都需重跑 20 闸门回归，且**必须改交付 harness**。

### §16.8 资源纪律
`/home` 仍 99%/2.8 GiB（低于 §6 红线），本轮**只写 `/data`**；
`TMPDIR`/`XDG_CACHE_HOME` 钉在 `/data`；所有 cell `nice -n 19` + `timeout 1500`。
本轮新增 11 个实验单元（4 个 nat2 + 7 个 nat3），单单元 ~115 s。

### §16.9 新增产物
| 文件 | 说明 |
|---|---|
| `harness_nat/run_cell_nat2.sh` | 支持 `--pinch-native-orientation` / `--pinch-native-blend` 的 runner |
| `harness_nat/wb_nat2_sweep.sh`、`wb_nat3_sweep.sh` | 两次扫描驱动 |
| `harness_nat/rep/wb_nat2_read.py`、`wb_nat2_geom.py` | 指标读取 / 几何诊断 |
| `nat2_sweep.json`、`nat3` 结果在 `harness_nat/rep/out/wb_nat3_*` | 证据 |
| `harness_nat/rep/sonic_grasp.py` | 隔离副本（含 `--flat-pinch-relax`/`--pinch-native-*`），sha `929952b7…` |
