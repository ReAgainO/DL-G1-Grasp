
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
