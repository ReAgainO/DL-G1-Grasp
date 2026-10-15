# W4a_DESIGN — 真机闭爪构型注入点定位 + S1000 失败机制 + 对照基线

- 任务：20261008-221515-qoder-03c4673f / 子代理 ws4a（W4a）。产出归父会话 TASKID，不新建 claim。
- 机器：worker00039；Build：`ws4_migrate/rep_base`（= rep_fixE 自有副本，20261008-182000-qoder-7d11d1ae/rep_fixE 的完整复制 + BASE 已 sed 到自有路径）。
- 关键指纹（本次实测 sha256）：
  - rep_base `rep/sonic_grasp.py` = 1e2a8edd9667bc62ec7f50898a775c87af54e638bdb1ba43723cbf2334c09c74
  - rep_base `.flags_flat` = b1_frozen_flags.txt = S1000 `s_frozen_flags.txt` = 31d3d77548e91ce6deb2f93fff0df4afebb4d5c2d01c107e8080422795559d1a（三处逐字节相同）
  - S1000 车道（d266d3a9）b25 格 meta 记录：sonic_grasp=0e0435b6…（与 rep_base **不同**，见 §3.4）
- 只读源未写一个字节：所有 d266d3a9 / 7d11d1ae 目录仅读；聚合脚本只读 result.json（输出写自有沙盒）。

---

## 1. 子目标 1：闭爪目标注入点定位（文件:行号级）

### 1a. “手指闭合的目标构型”由谁生成、当前值是什么

链路（本 build 实际生效路径，全部为 rep_base 副本行号；源码 sha 见上）：

1. **静态闭爪 recipe**：`rep/source_physics_core.py:30` `CLOSED = [0., -.60, -.425, 1.40, .08, 1.40, .08]`（`OPEN` 在 `:29`＝`[0., -.70, -2., 1.40, .08, 1.40, .08]`；仅拇指 3 关节不同）。
   - `rep/sonic_grasp.py:224` `close_hand=core.CLOSED.copy()`；
   - `:233`（pinch_geometry 生效，flags 里 `--pinch-geometry`）`close_hand[2]=-.88`。
   - ⇒ 实际静态 recipe = **`[0., -0.60, -0.88, 1.40, 0.08, 1.40, 0.08]`**（关节序 = 模型 actuator 36..43：拇指 3 + 食指 2 + 中指 2，见 `sonic_grasp.py:187`、`source_physics_core.py:25,31`、`finger_control.py:18`）。
2. **自适应 IK 目标（本 build 真正下发的“闭爪目标”）**：`--adaptive-hand` 在冻结 flags 中 ⇒ `:439-444`：
   - `:441` 每 0.1 s（`step%50==0`）调用一次 `:442` `hand_goal=hand_solver.solve(d, cube_pos, cube_R, hand_goal, closure_normal, …)`；
   - 求解器 = `AdaptiveHand`（`rep/adaptive_hand.py:11-13` 构造：opponent=middle、preload 1.5mm、face_half 15mm；`:30-59` IK 解，`face_target` 在 `rep/finger_clearance.py:9-29`；输出 `best[1]`＝7 关节命令角，记录于 `adaptive_hand.py:58` 的 `command_rad`）；
   - `:444` `hand_command += clip(hand_goal-hand_command, ±0.003)`（500Hz ⇒ 1.5 rad/s 限速），`:448` → `finger_torques` 独立指 PD。
   - 即：**目标构型 = 几何 IK 输出**（拇指+中指两个 pad 对夹立方体两面，preload 1.5mm、面内半区 15mm、逐指限速追赶），不是 tripod 求解、也不是纯预设角；预设角只作 seed / 非自适应回退（`:437`）。
3. **当前值（实测，两 build 一致）**：S1000 `b25_00_00` 与 rep_base 复跑 `b25_00_00` 的 `result.json → adaptive_hand`：
   - `calls=143`，`last.command_rad = [-0.00139, -0.82425, -0.40189, 1.40, 0.08, 1.3515, 0.002]`
   - 即闭合终态：拇指引到 ≈(0, -0.824, -0.402)，中指 ≈(1.3515, 0.002)，食指(非对角指)保持 recipe (1.40, 0.08)；pad 目标误差 ≤1.42mm。
   - 该 7 元向量即“真机构型注入”要替换的对象（语义上与真机每指关节角一一对应）。

### 1b. 替换为外部给定每指关节角的（近似）最小改动

方案 A（推荐，硬注入；改动 ≈10 行，均在自有副本上）：

| # | 位置 | 改动 |
|---|---|---|
| 1 | `sonic_grasp.py:155`（run 签名） | 新增参数 `grip_target_json=None` |
| 2 | `sonic_grasp.py:619`（argparse，紧邻 `--grip-face-half-mm`） | 新增 `--grip-target-json PATH` |
| 3 | `sonic_grasp.py:233` 之后（pinch_geometry 块内，`hj` 已在 `:187` 定义） | `if grip_target_json is not None: close_hand=_load_grip_target(...)`（加载 JSON：接受 `{"grip_target_rad":[7 floats]}` 或裸 7 元列表；校验 shape=(7,)、有限、且落在 `m.jnt_range[hj]±0.002` 内，否则 raise） |
| 4 | `sonic_grasp.py:441` 的条件 | 加 `grip_target_json is None and (...)` 守卫 ⇒ 外部目标下 **不再**每 0.1s IK 重解，`:283` 已在 CLOSE 入口置 `hand_goal=close_hand(=外部目标)`，`:444` 限速、`:448` 力矩通路原样复用 |
| 5 | `sonic_grasp.py:594` 附近 | `result['grip_target_json']=dict(path=…,sha256=…,rad=[…],adaptive_bypassed=True)` |

- 证据路径（“打印或落盘该目标”，任一条即硬证据）：
  1. 加载处 `print('GRIP_TARGET_JSON', json.dumps({...}), flush=True)` → run_fixE.sh:43 把 stdout 落盘到 `raw/<NAME>.stdout.log`；
  2. `result.json['grip_target_json'].rad` + `result['adaptive_hand'].calls==0`（外部目标下求解器不被调用）；
  3. 既有落盘 `trajectory.npz['hand_reference']`（`sonic_grasp.py:475` 每 20 step 记录 `hand`，`:606` 存盘，25Hz）：末段应收敛到外部目标（±0.003/step 限速内）。
- 不碰物理/门/阈值；`--grip-target-json` 缺席时代码路径逐行等价（建议 W4b 用 `assert` 或缺省分支保证零扰动）。
- **不改 `.flags_flat`**（保持冻结 flags 逐字节，两臂可比）：把新 flag 通过 run_fixE.sh `:24-25` 的 EXTRA 注入，如 `[ -n "${GRIP_TARGET_JSON:-}" ] && EXTRA+=("--grip-target-json=$GRIP_TARGET_JSON")`；flag 文件与脚本的 sha 会进 `runtime_stamp`（`:40`），自然留证。
- 方案 B（备选/第二臂）：保留自适应求解但把外部构型作为 seed（只做改动 #1-#3+#5，不动 #4）。区分“目标值”与“接触跟踪”两种效应，成本相同，建议 W4b 二选一或先 A。
- 注意事项：改动 `close_hand` 会连带影响 `:284 closure_normal`（以 close_hand 姿态 FK 求闭合法向）、`:335` 传入 `select_native_branch` 的 `hand_recipe`（分支静态过滤里的 finger_replan_error 用它做 seed）——这正是“该构型进入全链路”的应有语义，需在 W4b 记录。

### 1c. `--grip-face-half-mm`、`--endpoint-seed`、`--branch-face-alignment/--face-aligned-servo` 的流转（本 build 实测）

- `--grip-face-half-mm`（argparse `:619`，默认 15）→ run 参数 `:155` → ① `AdaptiveHand(...,grip_face_half_mm*.001,...)` `:225` → `face_target` 面内半区（`finger_clearance.py:14`，仅影响 pad 在立方体面上的落点）⇒ **直接塑形闭爪 IK 目标**；② 分支搜索 `:335` `hand_face_half_m=grip_face_half_mm*.001 if branch_face_alignment else .015`；③ 落盘 `result['grip_face_half_mm']` `:566`。
  - run_fixE.sh `:25`：仅当 FACE≠0 才加该 EXTRA。**b25 全部 FACE=0（默认 15mm）**；S1000 c20f 层 FACE=8（8mm）。
- `--endpoint-seed`（+`--endpoint-seed-native`，argparse `:615`）→ 载入 `out/pinch-feasibility.json` `:260-266`（native 变体取 feasible pregrasp 记录中 `native_seed_deviation_rad` 最小者）→ 目标用途 `:370` `goal=endpoint` **仅当 `not clearance_approach`**；本 build flags 含 `--clearance-approach`（`.flags_flat` 第 35 行）⇒ **endpoint 不进入任何阶段的目标**，仅进 `runtime_stamp`（`:43` pinch-feasibility.json sha）与断言 `:261`（kinematic_servo+flat_pinch 满足）。⇒ 对本迁移实验是 provenance 字段，不是目标来源。
- `--branch-face-alignment`（argparse `:620`；断言 `:159`）→ 分支搜索 `:335 face_alignment=…` → `native_branch.py:192` 用 `face_ik` 替代普通 IK；hand 过滤 preload/面区切换 `:335`。`--face-aligned-servo`（`:620`；断言 `:160`）→ CLOSE 入口算面轴 `:339-343` → 5Hz 臂伺服 `:409-412` → 落盘 `:600-601`。**两者均不在 `.flags_flat` ⇒ 本 build 未启用**（“存在 flag、默认 OFF”）。它们只影响臂的参考，不直接改闭爪目标。

---

## 2. 子目标 2：S1000 小方块失败机制（零重跑，只读 d266d3a9）

数据：`/data/group4/20261008-125638-qoder-d266d3a9/S1000/rep/out/{b25_*,c20d_*,c20f_*}/result.json`（150+150+100 格全覆盖）。
脚本：`/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/ws4a_agg.py`（只读）；输出存 `ws4_migrate/logs/ws4a_agg.out`。

### 2.1 分布表

| 层 | n | success | fail_reason=NONE(跑完全程) | fail=two-finger contact timeout | 备注 |
|---|---|---|---|---|---|
| b25 (25mm) | 150 | **4 (2.7%)** | 138 (92.0%) | 12 (8.0%) | 与背景“25mm 2.7%”一致 |
| c20d (20mm) | 150 | 0 (0.0%) | 129 (86.0%) | 21 (14.0%) | |
| c20f (20mm, FACE=8) | 100 | 0 (0.0%) | 89 (89.0%) | 11 (11.0%) | |

失败类归并（b25，n=150）：

| 失败类 | n | 占比 | 证据 |
|---|---|---|---|
| 抬不起+滑移双红（lift≈0，slip 超门） | 97 | 64.7% | hold_min_lift 中位 -0.1mm、slip 中位 41.4mm（门 10mm） |
| 仅 `no_robot_table_contact_full_task` 红（物理抓取达成，被严格门卡） | 31 | 20.7% | lift 中位 126.3mm、slip 中位 3.9mm |
| 超时：CLOSE 两指接触 5s 未达（two-finger contact timeout） | 12 | 8.0% | fail_reason |
| 仅滑移红（抬起了但 slip≥10mm） | 5 | 3.3% | lift>72mm |
| 仅 two_fingers 红 | 1 | 0.7% | |
| SUCCESS | 4 | 2.7% | lift 121.3-134.6mm、slip 3.7-4.2mm |

- b25 red 门直方：two_fingers 115 / slip_1cm 114 / hold_7cm 109 / release_drop_6cm 109 / no_support 108 / clearance_4cm 108 / no_robot_table_contact 102。
- 跑完全程 134 格的 red_n：1 个门 31 格、2 个 2 格、3 个 4 格、5 个 1 格、6 个 43 格、7 个 53 格 ⇒ 强双峰：31 格“单门近成功” vs 96 格“体无完肤”。
- c20d/c20f：hold_7cm/two_fingers/no_support/clearance_4cm/release_drop_6cm **五门 100% 红**、slip 99% 红；跑完全程的格 lift 最大 -0.1mm（**从未抬起过**）；两指接触在 HOLD 窗口从未同时保持 ≥2（two_fingers 全红）。20mm 层的失败是“夹不起来”，不是“抬不稳”。
- 参考滤镜侧写（与 §3.4 相关）：b25 有 69/150 格（46%）出现 `reference_filter.certified_continuation_steps>0`（S1000 build 上 C2 滤镜 T 上界 6.687s 触发“继续认证段”回退）；c20d 57/150（38%）、c20f 31/100（31%）。全层 `correction_clipped_cells=0`、`max_plan_horizon_s≡6.687`。

### 2.2 最可能被“外部闭爪构型先验”改善的失败类（判断+理由）

1. **b25 的 97 格 lift+slip 双红（64.7%）——最优先**：这是夹持质量失败（闭合后方块被搓走/滑出，抬升≈0、slip 中位 41mm），指端目标构型直接决定接触点位置与法向，注入真机成功构型是最对症的干预。
2. **12 格 CLOSE 两指超时（8%）——次优先**：闭合 5s 内凑不出两指 >0.1N，同样是“指构型/指位姿”问题，构型先验可改变接触建立概率。
3. **c20 两层（0 成功、lift≡0）——理论最对症但先验样本最弱**：20mm 立方体在自适应 IK 目标下从未建立可抬起的两指夹持（two_fingers 100% 红）；但真机 20mm 成功率本身极低（背景：20mm 0/250），可提取的成功构型样本量少，W4b 预期收益不确定。
4. **最不可能受益**：31 格“仅 no_robot_table_contact 红”——这是 strict-execution 的机器人-桌子接触门（`sonic_grasp.py:536`），lift/slip 与成功格同档（3.6-4.2mm），属臂/全身干净度问题，指构型不改变它；此外本层无 approach/alignment 类失败（12 个超时都在 CLOSE 阶段，approach 全部通过）。

---

## 3. 子目标 3：对照基线（rep_base 上的 25mm 同格网复跑）

### 3.1 选格与来源（与 S1000 b25 同格网）

- 坐标出处：只读源 `S1000/jobs.txt`（格式 `NAME|EDGE|CX|CY|FACE|STEM|ORDER`）逐字取用。
- b25 格网 = 8 x 值（0.2660→0.2954, Δ0.0042，行号 00,02,…,14）× 20 y 值（-0.1480→-0.0834, Δ0.0034，列号 00..19）。
- 参考动作：jobs STEM='-' ⇒ 不设 `N1_MOTION_STEM` ⇒ 默认 `near_s42`（run_s1.sh:34 / run_fixE.sh:26 / sonic_grasp.py:172）；已核 S1000 meta `motion_stem=near_s42`，且两树 `near_s42.npz` sha 相同（78eac68c…）。
- FACE=0 ⇒ 无 `--grip-face-half-mm` EXTRA（默认 15mm）。

选中的 5 格（覆盖 成功/近成功/超时/失败 × 参考滤镜敏感性 两个维度）：

| 格 | CX | CY | S1000 结局（fallback 次数） |
|---|---|---|---|
| b25_00_00（试水格） | 0.266000 | -0.148000 | 近成功（仅桌子门红），fallback=43 |
| b25_04_01 | 0.274400 | -0.144600 | SUCCESS，fallback=30 |
| b25_12_04 | 0.291200 | -0.134400 | SUCCESS，fallback=0 |
| b25_02_06 | 0.270200 | -0.127600 | 近成功（仅桌子门红），fallback=0 |
| b25_00_10 | 0.266000 | -0.114000 | 失败：two-finger contact timeout，fallback=0 |

运行命令（nohup，至多 2 格并行，核从 ws4_idle.py 的空核里挑；CUT=1791469822）：
`bash run_fixE.sh <NAME> 25 <CX> <CY> 0 - <cpu1,cpu2>`

### 3.2 读数（rep_base 复跑）与 S1000 同格并列

（下表由本次实跑填入，tally 见 `ws4_migrate/logs/` 与 rep_base/fixE_tally.csv）

| 格 | S1000 succ/fail | S1000 lift/slip(mm) | S1000 red / fallback | rep_base succ/fail | rep_base lift/slip(mm) | rep_base red / fallback | 判定 |
|---|---|---|---|---|---|---|---|
| b25_00_00 | False/None | 132.9 / 3.61 | table-gate / 43 | False/None | 133.0 / 3.62 | table-gate / 42 | 同类复现（maxT 6.687→8.024） |
| b25_04_01 | True/None | 123.8 / 3.78 | [] / 30 | True/None | 123.8 / 3.78 | [] / 30 | 同类复现；slip 差 3e-7 m，qpos 后段发散 ≤2.2e-2 rad |
| b25_12_04 | True/None | 121.3 / 4.24 | [] / 0 | True/None | 121.3 / 4.24 | [] / 0 | **trajectory.npz 逐位相同** |
| b25_02_06 | False/None | 121.5 / 3.69 | table-gate / 0 | False/None | 121.5 / 3.69 | table-gate / 0 | **逐位相同** |
| b25_00_10 | False/two-finger contact timeout | — | 13 门红 / 0 | False/two-finger contact timeout | — | 13 门红（同名同数）/ 0 | **逐位相同** |

全部 5 格 rc=0，wall 145-230s（并行/满载下）。tally（CUT=1791469822）实测输出：

```
fixE stratum (mtime>1791469822.0): total=5 success=2
  SUCCESS b25_04_01 lift= 123.8 slip= 3.78
  SUCCESS b25_12_04 lift= 121.3 slip= 4.24
  fail=None(ran all phases)=2  still-approach-timeout=0  other-fail=1
  near-success (<=2 red gates):
    b25_00_00: lift=133.0 slip=3.62 red=['no_robot_table_contact_full_task']
    b25_02_06: lift=121.5 slip=3.69 red=['no_robot_table_contact_full_task']
  other: b25_00_10 fail=two-finger contact timeout red_n=13
  per-cell CSV -> rep_base/fixE_tally.csv
```

逐位核验（trajectory.npz，rep_base vs S1000 同格）：b25_12_04 / b25_02_06 / b25_00_10（3 格，均为 fallback=0）qpos、hand_reference、body_reference、actuator_ctrl **全部 bitwise equal**；b25_04_01 hand_reference 相同、qpos 后段发散（≤2.2e-2 rad）；b25_00_00 同类微移。

tally 命令：`cd rep_base && PYTHONDONTWRITEBYTECODE=1 python fixE_tally.py 1791469822`（CUT=首格启动前 epoch；fixE_tally 的 BASE 已 sed 到 rep_base，不会覆盖源）。

### 3.3 与 S1000 的入口可比性判断

- **相同**：`.flags_flat`（三处 sha 逐字节相同）、跑格脚本参数构造（run_fixE.sh ≙ run_s1.sh，均 `--branch-coverage` 常开 + 同 EXTRA）、`near_s42.npz`、native_branch/adaptive_hand/grasp_geometry 等模块 sha。
- **不同（22/25 运行时模块 sha 相同，3 个不同）**：
  1. `reference_filter.py:38`：S1000 `if T>8:break` vs rep_base `if T>8.4:break` ⇒ C2 参考滤镜最大尝试地平线 6.687s→8.025s。**这是唯一对 b25 物理有实质影响的差异**。
  2. `sonic_grasp.py:286`：rep_base 把 `time_limit_s=approach_timeout` 传入 ClearanceApproach。
  3. `clearance_approach.py`：把硬编码 26s 上界参数化（默认仍 26s）。
  - 2+3 组合：flags 里 `--clearance-branch-servo` 在 ⇒ approach_timeout=32s ⇒ rep_base 的 approach 时钟上界 32s，S1000 为 26s（超过会 raise）。但 S1000 全部 150 格无 approach 阶段超时/crash（12 个失败均在 CLOSE），实测未触界；效果是在 [26,32]s 区间 S1000 会崩而 rep_base 可能继续——对本格网无观测影响。
- **结论**：同格网、同 flags、同参考输入；**非全局逐位可比，但可精确分级**——实测 3/5 格（全部 fallback=0：b25_12_04、b25_02_06、b25_00_10）与 S1000 **逐位相同**（qpos/hand_reference/body_reference/actuator_ctrl），与“fallback=0 ⇒ 参考流一致”的先验一致；2/5 格（fallback>0：b25_00_00、b25_04_01）出现参考轨迹改写（maxT 6.687→8.024、fallback 43→42），结局类别与读数保持同档（slip 差 3e-7 m、lift 差 ≤0.1mm 级、后段 qpos 发散 ≤2.2e-2 rad）。⇒ **对照组选格优先 fallback=0（逐位断言可用）；fallback>0 的格只能做类别级 + 毫米级对照**。W4b 对比注入效应时，凡要引用 S1000 历史格，须先查该格 fallback 次数（本次已给 b25 全层名单：46% 受影响）。

### 3.4 基线格命令原文

```bash
cd /data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base
nohup bash run_fixE.sh b25_00_00 25 0.266000 -0.148000 0 - 97,98  > logs/b25_00_00.launch.log 2>&1 &
nohup bash run_fixE.sh b25_04_01 25 0.274400 -0.144600 0 - 61,62  > logs/b25_04_01.launch.log 2>&1 &
nohup bash run_fixE.sh b25_12_04 25 0.291200 -0.134400 0 - 39,127 > logs/b25_12_04.launch.log 2>&1 &
nohup bash run_fixE.sh b25_02_06 25 0.270200 -0.127600 0 - <空核> > logs/b25_02_06.launch.log 2>&1 &
nohup bash run_fixE.sh b25_00_10 25 0.266000 -0.114000 0 - <空核> > logs/b25_00_10.launch.log 2>&1 &
```

---

## 4. W4b 建议（不在本任务执行）

1. `rsync/tar` 复制 `rep_base` → `rep_ext`（保持 rep_base 纯净基线）；在 rep_ext 实施 §1b 方案 A 的 ≤10 行改动；run_fixE.sh 加 `GRIP_TARGET_JSON` env→EXTRA 透传（不改 `.flags_flat`）。
2. 目标向量接入规范：7 元、关节序=actuator 36..43（拇指 0-2、食指 3-4、中指 5-6）、单位 rad、范围以 `m.jnt_range` 实测为准；JSON 带来源标定指纹（子代理提取数据 sha）。
3. 先在同一 5 格基线上 A/B（外部构型 vs 无注入），再做扩展格网；对照判据以 §3.3 为准（类别级 + 读数级；fallback=0 格可加逐位断言）。
4. 优先注靶：b25 lift+slip 类与 CLOSE 超时类（§2.2）；另外建议加跑 1-2 个现有同格多次重复（同 build 重复性基线）以区分“注入效应”与“参考滤镜差异噪声”。
5. 区分两种注入语义（硬目标 vs 仅 seed，§1b 方案 A/B）；如真机数据只有单手 7 角而无 cube 位姿，方案 A 更匹配（不依赖在线立方体位姿）。
