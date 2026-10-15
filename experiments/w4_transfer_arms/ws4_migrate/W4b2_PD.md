# W4b2_PD — 官方手指位置伺服配方移植对照实验（臂2）

- 父 TASKID: 20261008-221515-qoder-03c4673f; 节点 worker00039 (S4000)
- 副本: `/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_pd`（rep_base 只读保留, 未动; rep_ext_cfg 属另一 worker, 未碰）
- 配方来源: unitreerobotics/unitree_sim_isaaclab @ e30c25b1 (`robots/unitree.py:154-171` ImplicitActuatorCfg stiffness=100 / damping=10 / armature=0.1), 即 W3 MIGRATION.md 的 M1
- 成功门未做任何改动; `.flags_flat` 与 rep_base **逐字节相同**; 新开关只经 run_fixE.sh 的 EXTRA 注入

## 1. 移植方式（实施 ≤15 行级别的功能改动 + 一个纯新增函数）

| 件 | 改动 | sha256 (冻结值) |
|---|---|---|
| `rep/finger_control.py` | 纯新增 `finger_position_torques()`: `torque = clip(kp*(q_target-q) - kd*qd, actuator_ctrlrange)`; 原 `finger_torques` 一字未改 | 1273d58789a6de0a841ed4a84cda58689baf17fa60e107d0a847eba4129ce889 |
| `rep/sonic_grasp.py` | `--finger-pd KP,KD`（默认 None）+ `--finger-armature A`（默认 0）; 原 448 行单一力矩下发点分支; XML 载入时给 7 个 `right_hand_*_joint` 写 armature（class hand_motor 0.01→0.1）; stdout 模式证据行 + result.json.finger_control 落盘 | 5d1bac788ced13ebb33e161fb5fbcf4580069d46c72492011b67ade7ffbdb50d |
| `run_fixE.sh` | `FINGER_PD`/`FINGER_ARMATURE` env → EXTRA（meta 的 sonic_grasp_args 行自动留痕） | 3f5cf46edd5fb082604616a91e27e02131dbb962fc5997a5b0b95d0fd2e5165d |

- **q_target 是现成的**：不加任何新目标源。位置包装接的是 sonic_grasp 原有 `hand` 变量（AdaptiveHand IK `hand_goal` + 0.003/step 限速后的 `hand_command`；非自适应相位=OPEN/close_hand/blend）。**解释变量=力矩律(+armature)，不是目标构型**——与另一 worker 的构型注入臂正交。
- **armature 走"载入时注入"而非常量改 XML 文件**：这是为满足"默认关闭=逐位旁路"的硬判据。若静态改 XML，冒烟(a) 必不相同。注入后 `out/<N>/g1_free_grasp.xml` 里 7 个手指关节可见 `armature="0.1"`（硬证据），stdout 亦有 `FINGER_MODEL right_hand_armature=[0.1×7]`；载入前 class 值 0.01 其余不动。
- 证据行实例（PD 格）：
  ```
  FINGER_CONTROL mode=position kp=100.0 kd=10.0 armature=0.1
  FINGER_MODEL right_hand_armature= [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]
  ```
  `result.json.finger_control`: max_track_err=0.191 rad / mean=0.00092 rad / ctrl_saturation=0.15%（见 §3）。

## 2. 冒烟三连（判据）

- **(a) 旁路逐位**：`b25_12_04` 无旗标 vs rep_base 同格：qpos/qvel/body_reference/hand_reference/decoded_motor_target/raw/applied/actuator_ctrl/phase/time **全部 EQUAL**；`wrist_target` 报 DIFF 但为 NaN≠NaN 伪影（both_nan=True, 非 NaN 2217 值全等）。⇒ 默认关闭零扰动成立。
- **(b) 位置分支证据**：stdout `FINGER_CONTROL mode=position kp=100.0 kd=10.0 armature=0.1` + `FINGER_MODEL [0.1×7]` + result.json.finger_control 落盘（上面字段）。
- **(c) 35mm 阳性对照**：`a35_00_06` PD=SUCCESS lift=122.1 slip=2.76（S1000 基线 success 128.7/3.80, 双方 fb=0）⇒ 无回归。

## 3. 结果矩阵（每格：基线 → PD，同格同层同坐标；fb=reference_filter certified_continuation_steps）

fb=0 双方（参考流一致，读数级可比，含逐位先验）以粗体判。

### 35mm 层（S1000 a35 层基线；三层选格：成功/近成功/双红各一，同在第 00 行 x=0.266000；全部 fb=0）

| 格 | 基线 succ/lift/slip/red | PD(100,10,arm0.1) | 判定 |
|---|---|---|---|
| **a35_00_06** | T / 128.7 / 3.80 / [] | T / 122.1 / 2.76 / [] | 保持成功（slip 更小） |
| **a35_00_10** | F / 129.4 / 3.83 / [table] | **T / 128.9 / 2.91 / []** | **近成功→全绿翻转** |
| **a35_00_15** | F / **-0.1** / 20.55 / [hold7cm,two_fingers,no_support] | F / **134.1** / 2.76 / [table] | **从未抬起→完整物理抓起**（仅剩严格桌子门） |

### 25mm 层（W4a rep_base 基线 5 格 + S1000 双红代表格 1 格）

| 格 | 基线 succ/lift/slip/red (fb) | PD succ/lift/slip/red (fb) | 判定 |
|---|---|---|---|
| b25_00_00 | F / 133.0 / 3.62 / [table] (42) | F / -0.1 / 19.51 / 7 红 (48) | **回归**（近成功→双红类）；fb>0 双方, 类别级 |
| b25_04_01 | T / 123.8 / 3.78 / [] (30) | F / 127.1 / 2.66 / [table] (17) | 成功→near（只差桌子门）；fb>0 双方 |
| **b25_12_04** | T / 121.3 / 4.24 / [] (0) | **F / two-finger contact timeout (0)** | **回归**：CLOSE 两指 5s 未达 |
| b25_02_06 | F / 121.5 / 3.69 / [table] (0) | T / 131.7 / 2.25 / [] (18) | 提升为成功；PD 侧 fb=18, 类别级 |
| **b25_00_10** | **F / two-finger contact timeout (0)** | F / 134.9 / 3.53 / [table] (22) | **超时→完整物理抓起**（仅剩桌子门） |
| **b25_00_14** | F / **-0.1** / 38.04 / 4 红双红类 (0) | F / 131.8 / 3.06 / [table] (0) | **从未抬起→完整物理抓起**（仅剩桌子门） |

b25_00_14 选格规则：S1000 双红主失败类（该层 64.7%）中 fb=0、slip 38mm 接近该类中位 41mm、与 00 行同列。

fixE_tally（CUT=1791471000, 9 格 PD）：
```
total=9 success=3
  SUCCESS a35_00_06 122.1/2.76;  a35_00_10 128.9/2.91;  b25_02_06 131.7/2.25
  near-success (<=2 red, 全为 no_robot_table_contact_full_task 单红):
    a35_00_15 134.1/2.76;  b25_00_10 134.9/3.53;  b25_00_14 131.8/3.06;  b25_04_01 127.1/2.66
  other: b25_12_04 two-finger contact timeout;  b25_00_00 7 红
```

## 4. 结论（如实）

1. **35mm 阳性对照通过且为正收益（3/3 干净对照）**：1 保持成功、1 近成功翻全绿、1 双红"从未抬起"格被救活到 134.1mm。与 M1 预期一致——位置伺服能把"构型已成立时的指端瞬态/保持质量"改善到门级可见。
2. **25mm 层净效应≈零（混向 3 升 3 降）**：矩阵成功 2→1（n=6 无统计力）。它**不是 20/25mm 短缺的主限制因素**这一主判断成立；但也不是无关——它改变了失败机制分布与"近成功"构型，需要与构型臂组合才能判净收益。
3. **机制观察（可检验的解释）**：
   - PD 把两类"夹不住" 变成"夹住了但机器人触桌"：b25_00_10（CLOSE 超时→lift 134.9）与 b25_00_14（双红→lift 131.8）、a35_00_15（-0.1→134.1）全部收敛到 `[no_robot_table_contact_full_task]` 单红。9 格中 4 格是这个签名（基线 b25 层该类比 31/150≈21%），提示**刚性位置通道让指垫更早/更硬地压到台面**（或让臂被允许走得更低），这是与"包围构型"无关的独立效应。
   - 反向的 b25_12_04（成功→CLOSE 两指超时）：ctrlrange ±0.7Nm 下 kp=100 使误差 >7mrad 即饱和 ⇒ 闭合近似"时间最优快合"，小方块被踢开；b25_00_00 的 lift -0.1/slip 19.5 同源。**方块越小，饱和快合的踢飞反作用越容易压过夹持收益**（35mm 未被踢飞、25mm 部分被踢飞）。
   - 一旦夹持成立，PD 的保持质量更好：所有抬起来的 PD 格 slip=2.25–3.53mm，普遍低于同格基线（3.6–4.2）；lift 亦普遍更高（131–135 vs 121–133）。跟踪指标 mean err 0.0009 rad、饱和时间占比 0.15%（饱和是瞬态而非全程）。
   - 结论口径：位置伺服配方**在"接触建立/保持瞬态"层是有效杠杆，但被 ±0.7Nm 的力矩盒与"快合踢飞"限住**——它与 W3 已关闭的"加力/mu"结论不矛盾：问题不是峰值力太小，而是通道刚度/阻尼结构与方块惯量的匹配。可否在不踢飞的前提下吃到保持收益（如 kp 降到 30–50、或闭合段限速/软接触）留作下一臂，未在本实验回答。
4. 与另一 worker 的 rep_ext_cfg（包围构型注入）**通道分离**：本臂固定目标构型、只换力矩律；负结果支持"构型臂"继续，正结果（35mm）说明两因子叠加时配方有非零边际。

## 5. 产物与复现

- PD 结果: `rep_ext_pd/rep/out/{a35_00_06,a35_00_10,a35_00_15,b25_00_00,b25_00_10,b25_00_14,b25_02_06,b25_04_01,b25_12_04}/`
- 旁路冒烟A: `rep_ext_pd/rep/out_bypass_smokeA_keep/b25_12_04/`（= 逐位证明件）
- 崩溃尝试留档: `rep_ext_pd/rep/out_broken_ws4b2/`（3 个早期实现 bug 的残目录, 均已定位修复）
- W4a 基线归档: `rep_ext_pd/rep/out_w4a_baseline_keep/`（5 格, rep_base 原件未动）
- tally: `rep_ext_pd/fixE_tally.csv` (CUT=1791471000)
- 渲染: `ws4_migrate/video_pd/`（见 §6）
- 复现单格:
  ```bash
  cd rep_ext_pd && FINGER_PD=100,10 FINGER_ARMATURE=0.1 \
    bash run_fixE.sh <NAME> <EDGE> <CX> <CY> 0 - <cpu1,cpu2>
  ```

## 6. 视频（仅 success=True 格）

- `video_pd/W4b2_pd_a35_00_10.mp4`（近成功→全绿翻转格）：745 帧 @12.5fps，sha256 `917f2d80b1413c3e84f14c146a9184ce14c7601df27d4dbf835e260c2562984e`
- `video_pd/W4b2_pd_b25_02_06.mp4`（b25 首成功格）：746 帧 @12.5fps，sha256 `b72dc55688e90dd30f803a14876ab1281f53154c5bb13582e2de98e4e286cc9c`
- 渲染法：FK 回放（qpos→mj_forward→render，不步进物理），osmesa（LD_LIBRARY_PATH 指 220500-codex lane 的 libOSMesa.so 软链）, 960×720, 每 2 帧取 1, 输出 12.5fps；解码帧数与 ceil(len(qpos)/2) 精确一致，抽帧 nonblack=1.000。详见 `video_pd/README.txt`。
- 参考只读: `/data/group4/20261008-182000-qoder-7d11d1ae/ws4_video/`（其 osmesa 配方未随包, 本次独立打通）。

## 7. 坑（本次实测）

1. `m.jnt_armature` 不存在 → 是 `m.dof_armature[hv]`（armature 存 per-DOF）。
2. 位置包装校验照抄了 finger_torques 的"7 数组"约束 → 标量 kp/kd 必须在函数内广播（或调用处 np.full）。
3. result 落盘时 `rows` 已是 ndarray → 条件里写 `and rows` 触发真值歧义异常（改 len(rows)）。
4. **跑格期间改源文件**会被 sonic_grasp.py:537 的 runtime_stamp 自检抓死（Runtime source/model drift）——跑了 132s 的格作废；代码必须先冻结再发批。
5. 重跑同格必须先挪走 `rep/out/<NAME>`，否则 REFUSE(rc=3) 且 **progress.txt 不留痕**；轮询时若旧 result.json 还在会误判"已完成"。
6. ssh 多行命令中不要出现裸单引号（本机 shell 会提前截断，导致远端命令碎裂/挂起 cat）。
