# W4c_PHYS — 官方（isaaclab）小物体物理配方 → MuJoCo 等价物：同格 A/B 对照

- 任务：20261008-221515-qoder-03c4673f / 子代理 ws4c（W4c）。产出归父会话 TASKID，未新建 claim。
- 节点：worker00039（Step 0 探针实测 `worker00039 2026-10-08 23:08:13`，rc=0）。
- 构建：`ws4_migrate/rep_ext_phys`（= `rep_base` 的 `cp -a` 副本；BASE 已逐项 sed 到自有路径，实测无残留 rep_base 引用）。
  `rep_base` 与源 `20261008-182000-qoder-7d11d1ae/rep_fixE` 全程只读；`rep_ext_cfg`/`rep_ext_pd`（他人）未触碰。
- 规则核对：AGENTS.md sha256=`9e2c073c2ad7b602…`（= 任务给定前缀）✓；未用 sudo / 裸 crontab；未驱动其它 CLI agent；单条 ssh ≤10 分钟；**并行 ≤2 格**（每格 2 核，`taskset`，驱动器自带 pid 记账）。

## 0. 一句话结论

> 把官方 M2 配方按本组尺度过翻译成 MuJoCo 等价物（**接触参数三件套 margin 1mm / solref 0.02 1 / impratio 10，子步 dt=0.0005**）后：
> **25mm 层 6 格：2/6 → 3/6 成功；"物理抓住且抬到 130mm 以上" 4/6 → 6/6；HOLD 内 slip 3.6–4.2mm → 0.5–1.4mm；2 处"抓不住"（两指超时 / HOLD 丢接触）变为抓住。**
> **20mm 层 4 个代表性失败格：0/4 → 3/4 抓住（抬起 136–144mm、slip 0.7–0.8mm、HOLD 两指接触 980/980），1/4 反而更糟（渗透 5.7mm、只抬 22mm）。**
> **消融（关键）：子步细分单独用是**有害**的（25mm 2/2 格崩：13 门红 / 超时）；接触三件套单独在 25mm 上就能复现全部收益；20mm 上必须两者同时改。**
> ⇒ **"数值性假失败"确实存在且有量级：以接触保真度为唯一变量的对照里，20mm 代表格 3/4 的失败机制被翻转为"能抓住"、25mm 2/6 的"抓不住"被翻转；但它不是"加密时间步"能修的，而是接触模型参数；且 0/250 不能全归因于数值（3/4 翻开后仍被真·臂-桌接触门卡住，1/4 配方副作用反向）。**

## 1. 被翻译的配方（逐项，含来源行号与接入点）

官方来源（ws3_static/MIGRATION.md M2 节，本组已核）：unitreerobotics/unitree_sim_isaaclab @ e30c25b1dffdf92ada1d6c8c1fe9a47bdde0fecc
- `tasks/…/pick_place_redblock_g1_29dof_dex3/env_cfg.py:145-163`：sim.dt=0.005、enable_ccd=True、num_substeps=4、contact_offset=0.01、rest_offset=0.001、num_position_iterations=16、bounce_threshold_velocity=0.01
- `common_scene/base_scene_pickplace_redblock.py:52-74`：方块 0.06m、mass 1.0、static/dynamic friction 10/1.5、restitution 0.01、contact_offset 0.01 / rest 0.0

本组现状（实测，rep_ext_phys/rep）：
| 项 | 本组实测值 | 官方 | 翻译动作 |
|---|---|---|---|
| 物理步长 | `scene_grasp_hand.xml` `<option timestep="0.002" integrator="implicitfast" cone="elliptic">` | dt 0.005 / 4 子步 = 有效 0.00125 | `--substep 4` ⇒ dt=0.0005、控制拍仍 500Hz（每拍 4 次 `mj_step`） |
| CCD | `<flag multiccd="enable"/>` **已开** | enable_ccd=True | 无需动作（等价物已在） |
| 接触余量 | 全模型 geom margin=0 | contact_offset 0.01 m | `--contact-margin 0.001`（1mm；10mm 对 20–35mm 方块=半宽量级，按本任务指令取 1mm） |
| 接触时间常数 | cube `solref="0.006 1"`、pads `solref="0.008 1"` | Isaac 接触刚度/阻尼 | `--solref 0.02 1`（MuJoCo 默认量级） |
| 摩擦锥约束比 | `opt.impratio=1`（默认） | num_position_iterations=16 | `--impratio 10` |
| 迭代数 | MuJoCo Newton 求解器（软约束）无同名项 | 16 位置迭代 | 用 impratio/时间常数覆盖（**不做逐项假冒**） |

改动位置（`rep/sonic_grasp.py`，patch 前 sha=1e2a8edd…=W4a 记录指纹 → patch 后 45f0c6d8…）：
建模型 `:164` 之后加 4 个开关的实际应用；主循环 `:449` 单次 `mj_step` → `for _ in range(substep)`；
`result['physics_recipe_w4c']` 落盘（仅在启用时写入，缺省不写新键）；argparse `:651+` 加 4 个开关。
**为什么打在 `sonic_grasp.py` 而不是 `source_physics_core.py`**：本链路（fixE 跑格）里 `source_physics_core` 只被当作
常量/校准模块用（`core.OPEN/CLOSED/PADS/gains/blend` + `prepare_model()` 仅用于生成手腕几何校准帧，见 `sonic_grasp.py:46-70`），
它自带的 `simulate()`（`:160-223`，内含 `assert model.opt.timestep==DT`）是历史单文件路线、**不在跑格路径上**；
真正建模型与推进物理的是 `sonic_grasp.py:164`（`MjModel.from_xml_path(scene_and_cal(...))`）与 `:296` 主循环里的 `:449 mj_step`。
故"物理准备点"= `sonic_grasp.py:164/449`（等价件），行号接入点与 W3 的 M2 参考方向一致。
`run_fixE.sh`（sha 3a3edc0d…→0c94de28…）：加 `W4C_PHYS` env → `EXTRA`（不动 `.flags_flat`）+ meta 记 `w4c_phys_args=` + `W4C_TIMEOUT`（默认仍 900）。
**模型 XML 未改**：实测同格两臂 `scene.xml`/`g1_free_grasp.xml` sha256 逐字节相同（b25_12_04 e9b180d3…、b25_00_00 211b3d6a…、c20d_10_03 e98f9ce2…，robot 86713c23…）——物理差异只来自运行期 solver/接触参数。

## 2. 冒烟（三判据，全部通过）

(a) **默认行为逐位回归**（判据核心）：`b25_12_04__base`（不启用）vs W4a 基线 `rep_base/rep/out/b25_12_04`：
`qpos(1549,57)/qvel/body_reference/hand_reference/wrist_target/decoded_motor_target/raw_decoded_motor_target/applied_motor_target/actuator_ctrl/time` **全部 bitwise=True max|d|=0.000e+00**，phase 序列同，`success/lift/slip/max_lift/duration` 全等，gates identical。
同一断言又对 5 个 W4a 同格各自复核（`b25_00_00/04_01/12_04` 已跑，全部 `ALL ARRAY KEYS BITWISE EQUAL`）。
**4 个 20mm `__base` 臂与只读源 S1000 历史记录逐位相同**（c20d_10_03 / c20d_12_03 / c20f_09_01 / c20f_06_19：qpos/hand_reference/actuator_ctrl 逐位 + 门同名同数）⇒ 20mm 的 A/B 锚定在"发布过的 0/250 那一层"上，不是新物理。

(b) **启用确实生效**：`raw/b25_12_04__phys.stdout.log` 实测 `W4C_PHYSICS {…}`：
`physics_timestep_s=0.0005 / physics_hz=2000 / model_impratio=10.0 / geom_names=["red_cube_geom","right_thumb_fingertip","right_index_fingertip","right_middle_fingertip"] / geom_margin_m=[0.001]×4 / geom_solref=[[0.02,1.0]]×4`，同款写入 `result.json.physics_recipe_w4c`。

(c) **墙钟**：同格 base/phys = 127/148s（**1.17×**）；全批中位 **1.25×**（范围 1.14–1.42×）。细分只占总墙钟小头。

## 3. A/B 设计与选格（规则先写后跑）

- 25mm 6 格 = W4a 基线同格 5 格（b25_00_00 / 04_01 / 12_04 / 02_06 / 00_10）＋新增 1 格 **b25_10_17**。
  新增格规则（只读源 S1000 记录，脚本 `ws4c_select.py`）：`reference_filter.certified_continuation_steps==0`（fallback=0，参考流与 rep_base 可比）且结局属"抬不起+滑移双红"（W4a 统计里 b25 失败第一大 64.7%）的 **max_lift 最大格**。
  覆盖：2 成功 / 2 近成功(仅桌门红) / 1 两指超时 / 1 双红失败。
- 20mm 4 格（c20d/c20f 各 2）规则：fallback=0 中取 `max_lift_m` 前 2，且同层两格分属不同 slip 类（<40mm"夹住又丢" vs >100mm"拖出"）：
  `c20d_10_03`(.287,-.1378,FACE0)、`c20d_12_03`(.2912,-.1378,FACE0)、`c20f_09_01`(.2849,-.1446,FACE8)、`c20f_06_19`(.2786,-.0834,FACE8)。四格 base 臂与 S1000 逐位相同（见 §2a）。
- 每格两臂：base（无 W4C_PHYS）/ phys（`--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10`）；
  另加消融臂：`sub4`（只细分）、`soft`（只接触三件套）、`phys2`（重跑，确定性检查）。命名 `<cell>__<arm>`。
- 判据列：沿用 `fixE_tally.py`（success / red gates / lift_mm / slip_mm / fail）。数值代理口径见 §5。

## 4. 结果表（`fixE_tally.csv` + `logs/ws4c_summary.out` 同源）

### 4.1 25mm（n=6，同格同参考）

| cell | arm | wall_s | success | red gates | hold lift mm | slip mm | 2pad/HOLD | ΣF_min N | padPen mm | 2pad 连续段(≥25f) |
|---|---|---|---|---|---|---|---|---|---|---|
| b25_00_00 | base | 129 | False | 1 no_robot_table_contact | 133.0 | 3.62 | 980/980 | 1.15 | 0.747 | 2 (all 2) |
| b25_00_00 | **phys** | 148 | **True** | **0** | 134.1 | **0.62** | 980/980 | 1.57 | 0.576 | 1 (all 1) |
| b25_04_01 | base | 122 | True | 0 | 123.8 | 3.78 | 980/980 | 0.57 | 0.556 | 1 (all 1) |
| b25_04_01 | **phys** | 153 | **True** | 0 | 140.1 | **0.54** | 980/980 | 1.61 | 0.782 | 1 (all 1) |
| b25_12_04 | base | 127 | True | 0 | 121.3 | 4.24 | 980/980 | 0.51 | 0.491 | 5 (all 6) |
| b25_12_04 | **phys** | 148 | **True** | 0 | 142.2 | **0.51** | 980/980 | 2.00 | 1.275 | 2 (all 2) |
| b25_02_06 | base | 121 | False | 1 no_robot_table_contact | 121.5 | 3.69 | 980/980 | 0.70 | 0.486 | 5 (all 8) |
| b25_02_06 | phys | 146 | False | 1 **final_table_supported** | 129.9 | 0.97 | 980/980 | 0.89 | 0.719 | 1 (all 1) |
| b25_00_10 | base | 103 | False | **13**（含 completed,two_fingers,slip…）fail=**two-finger contact timeout** | — | — | **0/0** | — | 0.409 | 3 (all 6) |
| b25_00_10 | **phys** | 146 | False | **1 no_robot_table_contact** | **138.2** | **0.88** | **980/980** | 1.08 | 0.332 | 1 (all 1) |
| b25_10_17 | base | 122 | False | 6 hold_7cm,two_fingers,no_support,clearance_4cm,slip_1cm,release_drop_6cm | **-6.3** | **150.31** | **664/980** | **0.0** | 0.513 | 3 (all 10) |
| b25_10_17 | **phys** | 148 | False | **1 no_robot_table_contact** | **135.3** | **1.36** | **980/980** | 0.17 | 0.803 | 1 (all 2) |

要点：phys 臂把"两指超时"与"HOLD 丢接触"两格变成"抓住并抬 135–138mm、slip<1.4mm"，但这两格与 02_06 仍被**真·臂-桌接触**（4.82N / 3.99N / 02_06 的 final_table_supported）卡住；00_00 的 **15.25N 真接触在 phys 臂变为 0.0N** ⇒ 唯一一次 fail→success。
25mm 成功数 2/6 → **3/6**；"抓住（≤1 红）" 4/6 → **6/6**；HOLD 内三指合力最小值 ΣF_min base 0.51–1.15N → phys 0.17–2.03N（10_17 反而更低，02_06 抬升有限；不宣称"握力整体翻倍"）。

### 4.2 20mm（n=4，base 臂与 S1000 0/250 层逐位相同）

| cell | arm | wall_s | success | red gates | hold lift mm | slip mm | 2pad/HOLD | ΣF_min N | padPen mm | pen>0.5mm 拍 |
|---|---|---|---|---|---|---|---|---|---|---|
| c20d_10_03 | base | 123 | False | 7 | -1.1 | 32.59 | **0/980** | 0.0 | 0.398 | 0 |
| c20d_10_03 | **phys** | 157 | False | **1 no_robot_table_contact(1.39N)** | **136.3** | **0.71** | **980/980** | 1.00 | 0.726 | 64 |
| c20d_12_03 | base | 124 | False | 7 | -5.2 | 148.99 | 82/1000 | 0.0 | 0.484 | 0 |
| c20d_12_03 | **phys** | 162 | False | **1 final_table_supported** | **143.9** | **0.76** | **980/980** | 0.99 | 0.832 | 302 |
| c20f_09_01 | base | 132 | False | 7 | -5.5 | 147.02 | 330/980 | 0.0 | 0.427 | 0 |
| c20f_09_01 | **phys** | 151 | False | **1 no_robot_table_contact(1.20N)** | **144.1** | **0.70** | **980/980** | 2.03 | 0.940 | 625 |
| c20f_06_19 | base | 123 | False | 7 | -0.1 | 38.44 | 0/980 | 0.0 | 0.491 | 0 |
| c20f_06_19 | phys | 158 | False | **7（反向）** | **1.0** | 32.90 | **0/980** | 0.0 | **5.702** | **1790** |

要点：base 臂四格都是"抬起来过一次（max_lift 133–142mm）但 HOLD 里接触塌掉、方块掉回桌面"（HOLD 两指接触 0–330/980，ΣF_min=0）。
phys 臂 3 格变成"HOLD 全程两指接触 980/980、握力 1.0–2.0N、抬 136–144mm、slip 0.7–0.8mm"，**但 20mm 层仍是 0/4 成功**——残留的红门是**真·臂-桌接触 1.2–1.4N** 或 `final_table_supported`。
第 4 格（c20f_06_19）反向：padPen 5.70mm（20mm 方块的 28%）、1790 拍 >0.5mm 渗透、只抬 22.5mm、手-桌 8.98N ⇒ **配方在该格有害**（1mm margin + 0.02 时间常数在 20mm/0.02kg 量级上把方块挤出去了）。

### 4.3 消融（归因，同格）

| cell | 臂 | args | success | red_n | hold lift mm | slip mm | ΣF_min N | 判读 |
|---|---|---|---|---|---|---|---|---|
| b25_00_00 | base | — | False | 1 | 133.0 | 3.62 | 1.15 | — |
| b25_00_00 | soft | margin+solref+impratio | **True** | **0** | 136.8 | 0.83 | 1.56 | **单靠接触参数即复现** |
| b25_00_00 | sub4 | 只 --substep 4 | False | **6** | **-0.1** | **17.38** | **0.0** | **只细分=崩**（丢抓） |
| b25_00_00 | phys | 四件全开 | True | 0 | 134.1 | 0.62 | 1.57 | — |
| b25_00_00 | phys2 | 四件全开（重跑） | True | 0 | 134.1 | 0.62 | 1.57 | **与 phys 逐位相同（确定性）** |
| b25_12_04 | base / soft / sub4 / phys | — | T / **T** / **F(超时,13红)** / T | 0 / 0 / 13 / 0 | 121.3 / 126.8 / — / 142.2 | 4.24 / 0.98 / — / 0.51 | 0.51 / 1.14 / — / 2.00 | 同向 |
| c20d_10_03 | base | — | False | 7 | -1.1 | 32.59 | 0.0 | — |
| c20d_10_03 | soft | 三件套 | False | 7 | **0.9** | 31.76 | 0.0 | **单独不够**（padPen 1.61） |
| c20d_10_03 | sub4 | 只细分 | False | 7 | **-0.1** | 36.06 | 0.0 | **单独不够** |
| c20d_10_03 | phys | 四件全开 | False | **1** | **136.3** | **0.71** | 1.00 | **必须同时改** |

`phys2` 与 `phys` 全部数组逐位相同 ⇒ 启用臂也是确定性的，"翻转"不是运气。

## 5. 数值代理口径与观测（怎么量"接触丢失/穿透"）

口径（脚本 `ws4c_metrics.py`；均以 500Hz 控制拍为单位，telemetry 一行=一拍）：
- **LOADED pad** = 该拍 pad-cube 法向力 > 0.01N（与成功门 `two_fingers` 同一阈值；另报 0.1N）。
- `2pad/HOLD` = HOLD 窗口内同时两指加载的拍数 / HOLD 总拍数（门的逐步版）。
- `ΣF_min` = HOLD 内三指法向力之和的最小值（"握力是否塌到 0"）。
- `padPen` = -min(`contact.dist`) 于 pad 类接触行（负=穿透）；`pen>0.5mm 拍` = 每拍最小 pad 距离 < -0.5mm 的拍数。
- `2pad 连续段` = 全run 内 ≥25 拍（50ms）的两指接触连续段数（**接触碎裂度=抖振**指标；括号内为含短段的总数）。
- 接触丢失时刻：首段持续两指接触之后第一段 ≥25 拍的 <2 指（脚本另给 loss_at 时间与当时方块高度）。

观测（写实）：
1. **接触丢失是真存在的，但主要在 20mm 层与 25mm 的 10_17 格**：base 20mm 四格 HOLD 两指 0–330/980、ΣF_min=0（方块掉回桌面）；10_17 base 664/980、ΣF_min=0。phys 后这些格全部 980/980、ΣF_min 0.17–2.03N。**25mm 的 00_00/02_06/04_01/12_04 base 臂没有接触丢失**（980/980），它们的失败是别的（真·桌接触 / 抓取质量）。
2. **穿透要分两类读**：MuJoCo 软接触本身有准静态渗透——**base 臂也有**（pad 0.40–0.75mm；方块-桌 2.86–3.92mm，最深处在 RELEASE 落到桌面时的冲击压缩，Fn 仅 0.15–0.18N）。phys 臂把它放大（pad 0.58–1.28mm、20mm 上最坏 5.70mm、桌 5.5–6.1mm），这是 solref 时间常数变软（0.006/0.008→0.02）的**预期副作用**，不能当"数值故障"读；反过来它是"官方配方照搬会咬到自己"的证据（20mm 方块被 1mm margin + 0.02 时间常数挤飞，见 §4.2 第 4 格）。
3. **抖振/握力（实测，不夸大）**：base 臂两指接触碎裂（c20f_09_01 全 run 13 段 vs phys 1 段；00_00 2 段 vs 1 段）。**LIFT 段三指合力（中位）**：c20d_10_03 base 0.299N → phys 1.079N、c20d_12_03 0.990→1.062、c20f_09_01 1.127→2.042、c20f_06_19 0.466→(phys 中位 0.074 / 均值 2.083 / 峰值 8.771=挤飞)。⇒ 握力差异 1.1–3.6× **不是所有格一致**；c20d_12_03 base 以 0.99N 握力仍丢手，说明丢手不只取决于握力大小，**接触连续性（碎裂）与 LIFT→HOLD 交接**同样关键——本报告只用 `2pad/HOLD`、`ΣF_min`、`连续段数` 三个直接量做判据，不用"握力必然翻倍"这类外推。
4. 方块 max_lift 可达 133–142mm 而 HOLD 抬起 ≈0（20mm base）⇒ 失败发生在 **LIFT→HOLD 交接处丢手**（c20d_10_03 base 实测：t=54.156s 两指力 0.045→0、方块从 141.6mm 自由落体回桌，落速 ~1.6m/s 合自由落体）。

## 6. "数值性假失败占比"判断（本任务的答案）

定义（本报告用）：以"接触保真度"为唯一变量做同格对照，若失败臂的记录中带数值性征候（HOLD 接触塌到 0 / 两指接触碎裂 / 5s 内建不起两指接触）且高保真臂把该格变成"抓住"，则记为**机制级数值性假失败**。

- **20mm 层（n=4 代表格，base 与 0/250 层逐位相同）**：**3/4** 属机制级数值性假失败（c20d_10_03 / c20d_12_03 / c20f_09_01：base HOLD 两指 0–330/980、ΣF=0 → phys 980/980、抬 136–144mm）；**1/4 反向**（c20f_06_19：配方副作用使渗透 5.70mm、只抬 22.5mm）。注意：翻正的 3 格**仍不是成功**（残留真·臂-桌接触 1.2–1.4N 或 final_table_supported）⇒ 20mm 层 0/250 **不能**整体归因于数值。
- **25mm 层（n=6）**：**2/6** 带数值性征候（b25_00_10 两指超时 13 红 → phys 抬 138.2mm；b25_10_17 HOLD 丢接触 → phys 抬 135.3mm），**1/6**（b25_00_00）由"真·15.25N 手-桌接触"变为 0N 而翻成完全成功；其余 3 格（04_01/12_04/02_06）的失败/成功不因数值而生，但**抓取质量**系统性受数值影响（slip 3.6–4.2mm → 0.5–1.4mm，握力 0.51–0.70N → 0.89–2.00N）。
- **量化口径的另一个角度**：物理抓取达成率（≤1 红）25mm 4/6→6/6、20mm 0/4→3/4 ⇒ 代表性失败格里约 **5/10 的"抓不住"是接触保真度问题**；但这 5 格里最终能翻成 success 的只有 1 格（25mm 00_00），其余被真·接触门卡住。
- **修法结论（反直觉、必须上报）**：M2 建议动作里"高频子步"**单独用会显著变差**（25mm 两格全崩：13 门红/超时）；有效的是**接触参数三件套**（25mm 单靠它即复现全部收益），20mm 上则**必须**三件套+细分同时开。⇒ 官方的"dt 0.005×4 子步"不能照抄成"把 dt 再细分"；官方有效 dt=0.00125 恰好落在本组 base(0.002) 与 sub4(0.0005) 之间，配方要的是**接触参数与 dt 的匹配**，不是单向细化。

## 7. 限制与诚实边界

1. 无真值：slip/握力"变好"只说明保真度敏感，**不能证明**哪一臂更真；本报告只用它做"失败机制是否为数值性"的判定与量化。
2. 25mm 只 6 格、20mm 只 4 格（预算内），是**抽样**判断，不能直接外推 0/250 的整层比例；20mm 层的 3/4 与反向 1/4 都写进结论。
3. 配方是 4 个开关的**联合臂**；消融只做了 3 格（25mm×2、20mm×1），且未拆 margin/solref/impratio 三者各自的贡献（后续若要做，建议 20mm 格上做 margin×solref 的 2×2）。
4. `--contact-margin 0.001` 是按任务指令的尺度折中（官方 0.01m 对本组 20–35mm 方块=半宽量级，属不可直接照抄项），已在 §1 明示。
5. 门/阈值/成功判据**一字未改**；`rep_base`、`.flags_flat`、他人目录均未写；`phys2` 逐位复现保证"启用臂可重放"。

## 8. 产物与复现

- 构建：`ws4_migrate/rep_ext_phys`（rep_base 副本 + patch；`rep/out_ws4a_baseline/` 存放 W4a 旧的 5 格+e35n 锚点，另存 `fixE_tally_ws4a_snapshot.csv`）
- 脚本：`ws4c_patch.py`（增量改法+计数校验）`ws4c_select.py`（选格）`ws4c_drive.sh`/`ws4c_drive2.sh`（≤2 格驱动+pid 记账）`ws4c_metrics.py`（数值代理）`ws4c_cmp.py`（逐位对拍）`ws4c_agg.py`/`ws4c_summary.py`（出表）`ws4c_render.py`/`ws4c_render2.sh`（mp4）
- 结果：`rep_ext_phys/rep/out/<cell>__<arm>/`（result.json/trajectory.npz/telemetry.csv.gz/cube_contacts.csv.gz/scene.xml…）、`rep_ext_phys/fixE_tally.csv`、`logs/ws4c_summary.out`、`logs/ws4c_*.launch.log`、`raw/<name>.meta.txt`（含 `w4c_phys_args=` 与 sonic_grasp sha）
- 视频：`ws4_migrate/video_phys/`（成功格 phys 臂 1–2 段 mp4 + sidecar json；渲染=记录态回放，非重积分）
- 单格复跑：`cd rep_ext_phys && W4C_PHYS="--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10" W4C_TIMEOUT=2400 bash run_fixE.sh <cell>__phys <edge> <cx> <cy> <face> - <cpus>`
