# W5b_ASSET_CHECK.md — 外网线索→本组资产核查 + 先例参数提取

- TASKID：`20261008-221515-qoder-03c4673f`（子代理 ws5b；S4000=worker00039，2026-10-08 22:27 起）
- 流水：`/home/group4/group4_dasc7606c/logs/20261008-221515-qoder-03c4673f/steps-ws5b.md`
- 只读源：`/home/group4/group4_dasc7606c/repos/sonic-bridge/`；`…/rep_mesh/FINDING.md`、`…/rep_fixE/FINDING.md`（7d11d1ae）
- 落盘：`/data/group4/20261008-221515-qoder-03c4673f/ws5_research/`（`repos/` 两先例 + `fk_open_probe.py` 实测脚本）
- clone 偏差说明：repo① 远端 `git clone` TLS 中断、repo③ clone 不完整（无 commit），改用 codeload `tar.gz --strip-components=1`（等价 depth-1 快照）。凭证 sha256：repo① `118dc0b6…feeb97`（g1_act.tgz）、repo③ `01db9d14…eacf51`（dex3rl.tgz）。

## 摘要

1. **32mm 不是几何天堑，也不是摩擦/限位截断**：FK 实测指尖跨距 OPEN=101.8mm、CLOSED=32.4mm、全范围最大 274.5mm；35mm 块只需 55mm 球心距。7d11d1ae 记的"32mm"= 闭爪目标位形的指端间距（实测 32.4mm 吻合），是**控制器位形/时序**问题（可修截断），改限位/摩擦收益≈0（§A）。
2. **isaaclab#132 不可直接迁移**：那是 Isaac/Dex1 资产（friction=200 vs PD 上限 19Nm 锁死；soft_factor 0.9）；本组 MuJoCo `frictionloss=0.1 N·m` vs 指爪力矩 ±0.7 N·m（仅 14%），无锁死；无 soft-limit 概念（§A.1/A.4）。
3. **两先例的最强参照**：③ 用 `kp=50/dampratio=1` 位置伺服 + `forcerange`（手指 ±1.4，拇指根 ±2.45）+ `grip_qpos` 预调 + 残差动作，50Hz；本组纯力矩 PD `kp=[4,1.8,1.2,4,2,4,2]` + 力矩 ±0.7——**刚度差一个量级、力限低一倍**。① 定量证明"闭爪假死"：ACT 执行窗口 5 步时屈曲目标恒 0.015 rad（永不动），25 步时 0.545 rad 并抬杯成功（§B）。
4. **Top-1 建议**：W4b 先做"方块尺寸自适应闭爪目标 + 半开预整形"（20mm：40mm 球心距；25mm：45mm），而非改限位/摩擦（§C）。

---

## §A 本组闭爪行程核查（对照 isaaclab#132）

### A.1 issue#132 原文措辞与适用面

来源：`https://github.com/unitreerobotics/unitree_sim_isaaclab/issues/132`（HTML 读；API 从本机/WebFetch 侧均 403 限流）。
标题："[Bug] G1 **Dex1** Sim dataset / sim stack: wrong task prompts, gripper friction lock, wrist-cam train–eval mismatch"。

逐字关键段：
- "Stock config: **friction=200.0** on gripper joints with tiny range ≈**[-0.02, 0.024]** rad."
- "Max PD torque ≈ stiffness × range ≈ **800 × 0.024 ≈ 19 Nm**. Friction 200 ≫ that → joints physically locked; published gripper state stuck near 0, cannot open/close."
- "Fix that works for us: **friction=200.0 → 0.0** (and verify left/right cmd paths independently)."
- "**soft_joint_pos_limit_factor=0.9** caps close at **~0.0223 vs hard ~0.0245**… Setting factor to **1.0** helps StackRyg grasp reliability."
- 跟帖（codexenterprise）："我之前也尝试过过这些调整,是有帮助,但是模型训练后依然成功率非常低."

适用面（重要纠偏）：针对 **Dex1**（非 Dex3）、**Isaac Sim 资产**（issue 提到的配置在 `unitree_sim_isaaclab/robots/unitree.py` 的 ImplicitActuatorCfg）。父会话转述的"少 2mm"原文是 0.0245→0.0223（单位 rad，≈10% 行程），"2mm"不是原文单位。

### A.2 本组对应物核查（只读，文件:行号+数值）

| #132 要素 | 本组对应物（物证） | 数值对比与结论 |
|---|---|---|
| friction=200.0（Isaac joint friction） | `sonic-bridge/g1/g1_29dof_with_hand.xml:20-21` `<default class="hand_motor">`：`damping="0.01" armature="0.01" **frictionloss="0.1"**` | 0.1 N·m vs 指爪力矩上限 ±0.7 N·m（ctrlrange，行 603-609）=**14%**，非锁死；#132 是 200 vs 19（=10×） |
| 关节 range ≈[-0.02,0.024] | 右手指关节 range（range 行 468/477/487/504/513/528/537，关节名在其上一行）：thumb_0 ±1.0472；thumb_1 [-1.0472,0.724312]；thumb_2 [-2.0944,0]；index_0/middle_0 [-0.191986,1.8326]；index_1/middle_1 [0,2.0944] | 行程远大于 #132 的"tiny range"；闭爪目标 thumb_2=-0.425 距硬限 -2.0944 还有 1.67 rad 余量 → **限位没有截断任何东西** |
| actuatorfrcrange | 行 468-543 各关节 `actuatorfrcrange`：thumb_0 ±2.45，其余 ±0.7；执行器 `<motor>`（560-610，力矩模式，无 kp），右手指 603-609 `ctrlrange` 同值 | 官方/menagerie Dex3-1 手指是 **±1.4**（见 §B ③），本组 ±0.7 =**低 2×**（见 §C-2） |
| soft_joint_pos_limit_factor=0.9 | MuJoCo 无此概念；控制器 `sonic_grasp.py:151` `dq*=min(1,.08/max(|dq|))` + `np.clip(q+dq,lo,hi)`，`lo/hi=m.jnt_range+margin`，margin=0.002 rad 仅用于 ARM 关节（`sonic_grasp.py:251/380`） | **不存在 soft-limit 截断**；手指命令路径只有速率限制（见 A.4 与 §C-3） |
| 指尖/夹爪摩擦 | 指尖球 `right_thumb_fingertip`/`right_index_fingertip`/`right_middle_fingertip`（行 493-495/518-520/542-544）：`type=sphere size=0.010 **condim=4 friction="2.0 0.02 0.002" solref="0.008 1"`；`scene_grasp_hand.xml` 方块 `friction=2.0 condim=4`、桌面/地板 1.0 | 本组 XML **已被修改过**（menagerie 原版指尖是 condim3）；④ 的"menagerie 默认 condim3、kp=500"对本组资产不成立（我们更强） |

补充（闭爪命令路径，供 §C）：
- 相位-目标：`sonic_grasp.py:437` —— APPROACH/DESCEND/ALIGN 段手目标=`core.OPEN`；CLOSE 段 `blend(OPEN, close_hand, e/close_seconds)`（close_seconds 默认 2s）。
- adaptive 路径限速：`sonic_grasp.py:444` `hand_command+=np.clip(hand_goal-hand_command,-.003,.003)`，dt=0.002 ⇒ **1.5 rad/s 上限**，且 `step%50==0`（0.1s）才重求解（文件内 `hand_reference_speed_limit_rad_s=1.5` 进 result.json，行 566）。
- 控制增益（同组资产只读）：`rep_fixE/rep/source_physics_core.py:150-151` `kp[HAND]=[4,1.8,1.2,4,2,4,2]`、`kd[HAND]=[.10,.07,.05,.06,.05,.06,.05]`；力矩由 `finger_control.py:21` 饱和到 `actuator_ctrlrange`（±0.7）。
- 开/闭位形：`runners/run_grasp.py:54-63` `RIGHT_HAND_OPEN=[0,-0.70,-2.00,1.40,0.08,1.40,0.08]`、`RIGHT_HAND_CLOSED=[0,-0.60,-0.425,1.40,0.08,1.40,0.08]`（食指+中指 4 关节开/闭**相同**，只动拇指）。

### A.3 FK 实测（`ws5_research/fk_open_probe.py`，mujoco 3.2.7，只读加载 XML）

指尖球心距（thumb↔index / thumb↔middle 对称）：

| 构型 | 球心距 | 自由间隙（球心距−2×10mm） |
|---|---|---|
| OPEN `[0,-0.70,-2.00,1.40,0.08,1.40,0.08]` | **101.8mm** | 81.8mm |
| CLOSED `[0,-0.60,-0.425,1.40,0.08,1.40,0.08]` | **32.4mm** | 12.4mm |
| index↔middle（恒定） | 57.0mm | 37.0mm |
| 拇指扫全范围，index/middle 钉住 [1.40,0.08] | max **146.4mm** | — |
| **全 7 关节范围网格搜索** | max **274.5mm**（cfg=[0,0.7243,0,-0.192,0,-0.192,0]） | — |

抓取需求（指尖球 r=10mm，对置面接触）：方块 s 需球心距 ≥ s+20mm ⇒ 20mm→40、25mm→45、35mm→55mm。**OPEN 位形 101.8mm 对三类方块都有 2× 以上富裕。**

### A.4 "爪口固定 32mm"复核与分档判断

rep_mesh FINDING 原文："**爪口宽度是"固定 32mm<35mm"**：该手在开/闭位形里食指+中指关节值相同（[1.40,.08]），两指尖球间距 ~32mm（= 2×(17.5+10−1.5)），小于方块边长 35mm ⇒ 任何"横向平推入位"都会先接触、先拖拽"。

复核结论：
- "~32mm" 与本次 FK 的 **CLOSED 位形 32.4mm 吻合**；括号内算式实际=52（该式算的是"预载 1.5mm 接触时所需球心距"），原文算式与 32 自相矛盾（留档纠偏）。
- 该 32mm 是**闭爪目标位形的间距**，开爪位形已有 101.8mm、全范围可到 274.5mm ⇒ **不是几何开口上限**。
- 摩擦侧：`frictionloss=0.1` vs 力矩 0.7，无锁死、无"少 2mm"式软限截断 ⇒ **也不是被摩擦/限位截断**。
- **分档判断：可修截断**（根因是"闭爪目标过深 + 时序/位形"，不是机构或摩擦）。附带机制提醒：rep_mesh 的 M2s 刮块发生在该臂"加了 7 根指骨 mesh 碰撞 + 爪常态进路"的语境；本组 R3 成功路线的既有结论是 pads-only（指节幽灵），两者不可混表。

### A.5 "改这条参数会怎样"（给 W4b 的判据）

| 候选改动 | 预期 | 判定 |
|---|---|---|
| 放宽手指 range（限位） | 开爪 101.8mm 已远富余；闭爪由目标值而非限位决定 | **收益≈0，不做** |
| 降 frictionloss（0.1→0.02） | 0.1/0.7=14% 非瓶颈；降了只会影响保持死区 | **收益低，不做**（除非 W4b 证据显示指爪"顶牛"力矩被损耗吃掉） |
| 加 soft-limit factor 之类 | 概念不存在；MuJoCo 硬限位 | **不适用** |
| 改闭爪目标位形/尺寸自适应/预整形 | 直击"顶牛-滑脱/过闭"力学 | **做**（§C-1） |
| 提 kp/力限（对齐官方 ±1.4、kp≈50 档） | 本组刚度低一个量级、力限低 2× | **做**（§C-2） |
| 闭爪时序/执行窗口纪律 | 1.5 rad/s 限速 + 0.1s 重求解节拍 ⇒ 闭爪生效慢 | **做**（§C-3） |

---

## §B 先例参数提取（可执行粒度）

落点 `/data/group4/20261008-221515-qoder-03c4673f/ws5_research/repos/`：`g1-dex3-act-grasping/`（①，9.9MB）、`unitree-dex3-rl/`（③，12MB）。

### B.1 ① g1-dex3-act-grasping（G1+Dex3 白杯抓取，MuJoCo+ACT）

- **闭爪"执行窗口"处理（核心）**：
  - 代码：`g1_dex3_act_grasping/policies/act_policy.py:99-171` —— `action_chunk`（ACT 一次预测 `config.chunk_size` 步）+ `chunk_index`，**当 `chunk_index >= execution_steps` 才重推理**（:129），否则 `requested_target = action_chunk[chunk_index]`（:162）、`chunk_index += 1`（:171）；`execution_steps` 超 chunk 直接 ValueError（:54-56）。
  - 证据数据：`act_window_comparison.json` —— 窗口=5：`max_index_middle_target_rad=0.0153`、`max_index_middle_actual_rad=0.0150`、`final_table_contacts=3`、抬升 0mm；窗口=25：target=0.5447/actual=0.5438、`max_continuous_10mm_clear_hold_s=1.006`、抬升 `23.88mm`、桌接触 0、三指载荷比 0.234。
  - 机制原话（README）:"执行窗口为5步时，ACT不断重新预测接近阶段，**手指闭合动作总被留在预测序列的未来**；改为执行25步后，闭合动作能够进入实际控制并完成抬杯"；CLI `--act-execution-steps 25`（README:137）；ACT 一次预测 100 动作、每执行 25 步重推（README:126-128）。
  - **对 W4b 的含义**：任何"预测未来"控制器（含若采用 ACT/VLA 产物）必须让闭爪段执行足够步数落地；判据 = target-vs-actual 屈曲曲线（他们做到了 target≈actual，5 步时两者一起≈0=假死）。
- **MuJoCo 模型来源**：**非 menagerie**。`envs/g1_cup_env.py:18` → `unitree_ros/robots/g1_description/g1_29dof_with_hand_rev_1_0.xml`；etree 改写：焊死 floating base+除右臂+Dex3 外全部关节（:35-47），保留原 actuator（:45-47），删 sensor/keyframe（:50-53），全部 geom 覆写 `solref="0.002 1"`、`solimp="0.95 0.99 0.001"`（:166-168）。控制侧为自有力矩 clip：`application.py:176` `data.ctrl[actuator_ids]=np.clip(torque,-torque_limits,torque_limits)`。
- **物体与成功判据**：杯=cylinder `size="0.036 0.05"`（r36×h100mm）、mass 0.12、friction 1.2、condim 4（`g1_cup_env.py:119-131`），杯底初始离桌 1mm。成功 = **杯最低碰撞点离桌 ≥10mm、无杯-桌接触、连续保持 ≥1.0s**（`project_results/fixed_position_single_trial.md`；`evaluation/success_metrics.py` 用 `geom("cup_geom")` 朝向投影算最低点）。结果：10 预置位各 1 次全 PASS（10.64–26.76s）；最难位 ±2mm 抖动 10/10（均值 25.3s）；同初态重复 5/5。
- **可借用纪律**：成功判据必须用"最低碰撞点+持续时长"，不用质心高度（他们对倾斜杯专门做了此防御）；抖动测试 ≥10 次同/近位置。

### B.2 ③ unitree-dex3-rl（Dex_Uni：Dex3-1 手指内转动骰子，PPO）

- **手模型**：Dex3-1 右手，"extracted from **mujoco_menagerie**"（README:18）。
- **执行器（训练用 `models/dex3_dice_scene_torque.xml:174-183`）**：7 个 `<position>`，全部 `kp="50" dampratio="1" inheritrange="1" forcelimited="true"`；
  `forcerange`：thumb_0 **±2.45**，其余 6 关节 **±1.4**；注释逐字："kp=50: stiff enough for tracking, RL-friendly proportional range"、"Per-joint forcerange from Unitree **menagerie actuatorfrcrange** specs"。
  （另一份 `dex3_dice_scene.xml:44` 是 `kp="30"`，非训练用。）
- **关节物理**：`<joint armature="0.01" frictionloss="0.3" damping="0.3"/>`（torque 版，行 45）。
- **关节范围（比本组窄）**：thumb_2 [-1.74533, 0]（本组 -2.0944）、middle_0/index_0 [0, 1.5708]（本组 [-0.191986, 1.8326]）、middle_1/index_1 [0, 1.74533]（本组 [0, 2.0944]）。
- **指尖接触**：球 r=10mm，torque 版 `condim=3 friction="0.8 0.05 0.001"`（行 99-100/122-123/144-145）；旧 scene 版 condim=4 friction 1.0-1.5。
- **物体**：骰子=box half 0.02（**40mm**）mass 0.05kg、friction 0.8、condim 3（行 161-163）；可视 mesh `dex_cube.obj` bbox ±1 × scale 0.02 ⇒ 40mm（**"16mm 骰子"的说法不成立**，实测更正）。
- **grip_qpos 构造与残差动作**：
  - `envs/dex_cube_env.py:130-131`：`# Tuned via scripts/tune_grip.py with kp=50…`；`self.grip_qpos = np.array([-0.5,-0.4,-1.2,0.85,0.8,0.85,0.8])`；
  - 动作：`ctrl = grip_qpos + action * action_scale`（:283-285），`action_scale` 默认 0.3（:135），v7 配置 0.15；action=0 即保持预调握姿（README:"Native position actuators with residual action space (action = 0 holds the grip)"）；
  - 另有 tune 脚本实测配方 `scripts/tune_grip.py:24` `CURRENT_GRIP=[-0.419,-0.339,-1.047,1.100,1.222,1.100,1.222]`（比 env 默认更闭）；预握时序：`open_qpos(0)→grip_qpos` 线性插值入握（:244-256）。
  - 关节序：thumb_0/1/2, middle_0/1, index_0/1（tune_grip.py:19-21）。
- **课程（configs/ppo_v2_runpod.yaml:57-217）**：`GRIP → MICRO_ROTATE → GAIT_EMERGE → MED_ROT → SINGLE_90 → MULTI_90 → MULTI_TARGET → EXPAND_TARGET → ALL_FACES`；每相位 `min_updates_override` 50→1500、相位推进以 eval SR 为准（v5 修复注释）。**"先 GRIP"确认**。
- **控制频率**：`timestep=0.002`（torque xml:3）× `frameskip=10`（yaml:6 与 env:71）⇒ **50 Hz 决策**；episode ≤150 步；256 envs；obs 48 维（env:166-167）。
- **成功/奖励要点**：`goal_threshold: 0.25`（rad，面朝上误差阈值，v6 从 0.05 放宽）、`drop_penalty -100 / drop_height 0.03`、`goal_bonus 100`（yaml:34-42）。

### B.3 参数对照表（他们 vs 本组）

| 项 | ① ACT 杯 | ③ RL 骰子 | 本组（sonic-bridge + rep_fixE 控制器） |
|---|---|---|---|
| 手模型源 | unitree_ros g1_description（非 menagerie） | menagerie Dex3-1 提取 | menagerie 系 `g1_29dof_with_hand.xml`（已改：指尖 condim4/friction2.0） |
| 执行器 | 保留原 XML，控制侧力矩 clip（application.py:176） | `<position kp=50 dampratio=1>` ±2.45/±1.4 | `<motor>` 力矩模式；PD kp=[4,1.8,1.2,4,2,4,2] kd=[.10,.07,.05,.06,.05,.06,.05]；clip ±0.7（thumb_0 ±2.45） |
| 达到力限所需误差 | — | 0.028 rad | **0.175–0.58 rad**（全程近饱和） |
| frictionloss/armature | 原 XML（未列） | 0.3 / 0.01（damping 0.3） | 0.1 / 0.01（damping 0.01） |
| 指尖接触 | （solref 0.002 1 全局覆写） | r10mm condim3 friction0.8 | r10mm **condim4 friction2.0 solref 0.008 1** |
| 物体 | 杯 r36 h100 0.12kg f1.2 | 骰子 40mm 0.05kg f0.8 | 方块 35mm 0.02kg f2.0；（20/25mm 需 --direct-table） |
| 控制频率 | 25Hz 录制；ACT 预测 100、执行 25 步 | 50Hz（0.002×10） | mj_step 0.002（500Hz 内环）；闭爪=2s blend；adaptive 限速 1.5 rad/s、0.1s 重求解 |
| 闭爪构造 | ACT chunk 内的 7 手关节维 | grip_qpos 预调 + 残差 ±0.15~0.3 | OPEN/CLOSED 两定值（index/middle 开闭相同）+ 尺寸自适应(AdaptiveHand) |
| 成功判据 | 离桌 ≥10mm 持续 1.0s | 面误差 ≤0.25 rad | 20 道门（含 hold_min_lift/slip 等）；本任务取不到逐门清单 ⇒ 待 W4b 查 |
| 关键纠偏 | — | **非 16mm 骰子**（实为 40mm/50g） | 本组 ±0.7 力限比官方低 2× |

### B.4 线索纠偏汇总（原线索 → 核实后）

| 线索 | 核实结果 |
|---|---|
| ① "执行窗口 5→25 步才生效" | **成立**，且给出定量物证（act_window_comparison.json：0.015 rad 假死 vs 0.545 rad 抬杯） |
| ① "MuJoCo 模型来源是不是 menagerie" | **不是**；unitree_ros g1_description（对 W4b 是好消息：与本组资产同血统，参数可对照） |
| ② Dex3 / friction=200 | **是 Dex1 + Isaac 资产**；本组 MuJoCo frictionloss=0.1 无锁死；"soft_limit 0.9 少 2mm"原文是 rad 口径 0.0245→0.0223 |
| ③ "16mm 骰子" | **不成立**：实为 40mm/50g 骰子；"kp=50/dampratio=1、±1.4/2.45Nm、grip_qpos+残差、先 GRIP" | 
| ④ "menagerie 手指 condim3、kp=500" | 对**原版** menagerie 成立；**本组 XML 已改**为 condim4/friction2.0；本组无 XML 级 kp（力矩模式） |

---

## §C 给 W4b 的注入建议（按 预期收益/成本 排序）

### C-1（Top-1，低风险直击痛点）方块尺寸自适应闭爪目标 + 半开预整形
- **改什么**：W4b fork 的抓取控制器（`sonic_grasp.py` / `source_physics_core.py:30` 的 `CLOSED`；`--thumb-close` 已存在=source_physics_core.py:157）。用 `fk_open_probe.py` 的 FK 表把"接触球心距 = s+20mm − 2×preload"反解成 thumb_2（必要时含 thumb_1/index/middle）目标角：
  - 20mm 块 → 球心距 40mm；25mm 块 → 45mm（OPEN 101.8 与 CLOSED 32.4 之间插值确认角度）；
  - 在 DESCEND 前加"preshape 位形"= 目标开口 +5~10mm 余量，CLOSE 只走短行程。
- **为什么**：现 CLOSED(32.4mm) 对 20/25mm 是**过度闭合**（越过接触点 7.6~12.6mm 的深行程），rep_mesh 实测失败形态含"两指顶牛 17–21N 后滑脱"；小块被挤飞/扫走的力学来源就是过闭+深行程。
- **怎么证明**：20/25mm 各 ≥5 格 A/B（开/关该改动），读 `result.json`（success/失败相位）+ `contact-audit.json`（thumb/index/middle 力 + 方块横向位移，弹飞判据），35mm 基线跑惰性对照防回归。
- **前置门槛**（现成物证）：非 35mm 块必须 `--direct-table`（`sonic_grasp.py:654` 断言）；`cube_half` 硬编码点清单见 `sonic_grasp.py:595`（adaptive_hand.py:36、grasp_geometry.py:16/25、sonic_grasp.py:433）须核对随 `--cube-edge-mm` 生效。
- **风险**：低（不动物理常数、不动 20 道门；只改目标位形与时序）。

### C-2（中成本高上限）指爪增益/力限对齐官方 Dex3-1
- **改什么**：① `g1/g1_29dof_with_hand.xml:603-609` motor `ctrlrange`：6 个手指关节 ±0.7→**±1.4**（与 menagerie/官方 `actuatorfrcrange`、③ 的 forcerange 一致；thumb_0 保持 ±2.45）；② `source_physics_core.py:150` `kp[HAND]` 从 [4,1.8,1.2,4,2,4,2] 向 kp=50/dampratio=1 折算（建议先 2× 档试，kd 已有 √gain 规则）。
- **为什么**：本组"达满力矩需 0.175–0.58 rad 误差"=近似 bang-bang 弱伺服；③ kp=50 只需 0.028 rad。闭合到接触的速度与 HOLD 抗滑都受此限（对照 ③ 手指 ±1.4 vs 本组 ±0.7 = 低 2×）。
- **怎么证明**：同格 A/B 读 `hold_slip_m`/`hold_min_lift_m`/指爪力矩 telemetry；小块必须与 C-1 配对（力大了更容易挤飞小块）。
- **风险**：中——改的是物理常数，必须在 result.json 显式声明 `success_gate_change/physics_change`；可能使 e35n 45 成功的基线可比性失效 ⇒ 只开新臂，不动冻结件与 S1000/fixE 原件。

### C-3（低-中成本，纪律型）闭爪时序与执行窗口
- **改什么**：`sonic_grasp.py:444` 的 `±0.003 rad/步`（≈1.5 rad/s）+ 每 50 步重求解：在 CLOSE 段放宽为预计算目标直接阶跃（或 ≥4 rad/s），把"闭爪慢慢混入"改成"当步生效"。
- **为什么**：① 的定量教训——窗口不足时闭爪 target 与 actual 一起停在 0.015 rad（永远留在"预测未来"）；本组 1.5 rad/s 使 thumb_2 全程 1.575 rad 的摆动至少 1.05s，小块抓取窗口内方块易被前期接触扫走。
- **怎么证明**：记录 CLOSE 段 thumb_2/index_0 目标 vs 实际轨迹（照抄 ① 的方法）+ 首次接触时刻/capture 位移、`phase_changes` 时间戳。
- **风险**：低-中；务必吸取 rep_mesh M2o/M2p 教训（全展爪拖桌 20.4N、晚期展爪 ALIGN 发散 5→36mm）⇒ 只做"半开预整形"，不做全程展爪；整形必须在 ALIGN 收敛之后。

### 明确不做（省预算）
- 改手指限位 range、降 frictionloss、加 soft-limit：§A.5 判定收益≈0（无锁死/无截断/无该概念）。
- 把 menagerie 原版 condim3/kp500 搬来：本组指尖已 condim4+friction2.0（更强），XML 无穷位置执行器。

### 复现命令（只读/轻载）
```bash
# FK 实测（只读加载资产 XML；nice 19）
nice -n 19 /data/group4/20261004-205550-qoder-1280b420/env/bin/python \
  /data/group4/20261008-221515-qoder-03c4673f/ws5_research/fk_open_probe.py
# 先例快照（已在 repos/；如需重取）
# ① https://codeload.github.com/wge639286-debug/g1-dex3-act-grasping/tar.gz/refs/heads/main
# ③ https://codeload.github.com/Adithya191101/unitree-dex3-rl/tar.gz/refs/heads/main
```
