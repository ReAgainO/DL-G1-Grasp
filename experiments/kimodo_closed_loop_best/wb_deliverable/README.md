# G1 右手抓取方块 —— Kimodo 生成动作 + 程序控制抓取 + SONIC 闭环验证

- **事务编号**：`20261008-232029-workbuddy-34e89f61`
- **节点**：`group4@10.123.0.39`（S4000，MUSA）
- **共享工作区**：`/home/group4/group4_dasc7606c/work/20261008-232029-workbuddy-34e89f61/workbuddy/`（scripts / evidence / constraints）
- **大产物**：`/data/group4/20261008-232029-workbuddy-34e89f61/`
- **登记簿**：`/home/group4/group4_dasc7606c/logs/20261008-232029-workbuddy-34e89f61/steps.md`
- **遵守**：`AGENTS.md`（sha256 `9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36`）

---

## 〇 结论（一句话）

闭环控制**成功**：官方 SONIC harness 单元格 **`wb_kimo_p6l1` 20/20 门全部通过（`success = true`）**，
其中**右臂靠近方块**与**右臂抬升**两段参考动作均由 **Kimodo** 生成（分别来自 clip `p6_conv` / `l1_conv`），
抓取时刻的**手臂位置、手腕转向、手指闭合**由程序代码（官方 `DESCEND/ALIGN/CLOSE` 相位控制）执行，
**手指在靠近之前张开、抓住之后保持不变**，最终导出 **30 fps、root 固定 `[0,0,0.7887]`、四元数固定 `[1,0,0,0]`（wxyz）** 的抓取动作 CSV。

---

## 一 仿真环境（未自造环境，全部取自 SONIC 侧既有资产）

| 项 | 值 |
|---|---|
| harness 根目录 | `/data/group4/20261008-232029-workbuddy-34e89f61/harness_s1000/` |
| 控制器 | `rep/sonic_grasp.py`，sha256 `0e0435b66da9b9b5d56092246a0deda23c6b38fdac01f7d39e5a8496f14148b9`（**全程未改动**） |
| runner | `run_cell.sh`，sha256 `6f9f44e2b19118b5c040b5d9107400231374d0cf44f43e2d243ce841698555da` |
| 场景 | `rep/out/<cell>/scene.xml`（MuJoCo，Z-up 右手系，`nq=57 nv=55 njnt=45 nu=43`） |
| 方块 | `red_cube_free`，中心 `[0.267, -0.118, 0.7745]`，边长 35 mm |
| 桌面 | `table_top` z = 0.725 |
| 目标手 | 右手（qpos `36:43` 右臂、`43:50` 右手 7 指） |
| 冻结 flag 列表 | `harness_s1000/.flags_flat`，经 `run_cell.sh` 逐字传入（含 `--clearance-approach --clearance-native-branch --clearance-branch-servo --branch-coverage --pinch-geometry --phase-clips --c2-reference --kinematic-servo --grip-frame-lift --lift-height .15 --close-seconds .5 --capture-radius .007 --strict-execution --reference-fallback --endpoint-seed --endpoint-seed-native --contact-close --adaptive-hand --direct-table --surface-capture --gravity-arm 1 --finger-gain 3 --contact-entry-dwell .04 --neutral-shoulder-offset .2 --opponent middle --grip-preload-mm 1.5 --table-front .24`） |

复现命令（唯一入口）：

```bash
bash /data/group4/20261008-232029-workbuddy-34e89f61/wb_loop3.sh p6_conv l1_conv wb_kimo_p6l1
```

---

## 二 按要求在 Kimodo 推理中启用 MUSA 注意力补丁

### 2.1 补丁来源
- 报告：`reports/20260929-1605-qoder-attnfix-report.md`（任务 `20260929-1605-qoder-attnfix`）
- 交付模块：`work/20260929-1605-qoder-attnfix/musa_manual_attn.py`（3449 B）
- 报告结论：本 MUSA（S4000）节点上 fp32 `scaled_dot_product_attention` 会静默返回 fp16 级结果
  （单算子相对误差 `4.21e-04` vs CPU `4.46e-08`）。修复必须**两步同时**做：
  1. `torch.backends.mha.set_fastpath_enabled(False)` —— C++ 融合 MHA 快路径会绕过 Python 补丁；
  2. 用手写 fp32 实现替换 `F.scaled_dot_product_attention`。
  实测 Kimodo 去噪器端到端相对误差 **`4.694e-03 → 7.741e-06`（606×）**，运行时 +4%。

### 2.2 集成方式（按报告 §五.1 的 import 用法）
新增包装脚本 `workbuddy/scripts/wb_gen_fix.py`，在**运行官方未改动的** `kimodo/scripts/generate.py`
之前完成两项修复，并在 `finally` 中打印状态、再 `disable()` 还原：

```python
FIXDIR = "/home/group4/group4_dasc7606c/work/20260929-1605-qoder-attnfix"
sys.path.insert(0, FIXDIR)
import musa_manual_attn as ma
ma.enable(verbose=True)                       # 步骤 1+2
assert ma.status()["fastpath"] is False
```

### 2.3 生效证据（本次交付所用两个 clip 的生成日志）

| 日志 | 设备 | 补丁前 | 补丁后 |
|---|---|---|---|
| `kimodo_logs/reach_p6.log` | `Using device: cuda:0` | `{'enabled': True, 'fastpath': False, 'hits': 0, 'fallbacks': 0}` | `{'enabled': True, 'fastpath': False, 'hits': 3232, 'fallbacks': 32}`，随后 `restored: fastpath=True` |
| `kimodo_logs/lift_l1.log` | `Using device: cuda:0` | 同上 | 同上（`hits=3232, fallbacks=32`），`restored: fastpath=True` |

`hits=3232 ≠ 0` 说明手写 fp32 attention **确实在调用链上**（不是"打了补丁却从未被调用"的假成功）；
`disable()` 可完全还原，**未修改任何共享文件**。

### 2.4 附带修复：共享仓文本编码器回归（会让 Kimodo 输出完全失真）
`repos/kimodo` 存在**他人任务于 10-05 留下的未提交改动**，把 `llm2vec` 文本编码器预设从
Llama-3-8B 改到了 Mistral-7B，导致监督 LoRA 挂不上（`Found missing adapter keys …`），
文本条件失效，模型输出分布外下蹲动作（骨盆 0.40–0.50 m，正常应为 0.73–0.79 m）。

`wb_gen_fix.py` 的 R2 修复在**进程内**把预设改回已提交的 Llama-3-8B（`importlib.import_module`
取真正的模块，而非 `kimodo/model/__init__.py` 重新导出的同名函数），**不改共享仓任何文件**：

```
R2   base: .../Mistral-7B-Instruct-v0.2/snapshots/63a8b081…  ->  McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp
R2   peft: .../LLM2Vec-Mistral-7B-Instruct-v2-mntp/snapshots/e76f9757…  ->  …-Llama-3-8B-Instruct-mntp-supervised
```

修复后可用同一条官方命令（`"A person walks in a circle." --duration 4.0 --seed 0 --diffusion_steps 100`）
把队里的参考片段重放到 **root z 最大偏差 1.47 mm**（root xyz 偏差 `0.01456 / 0.00379 / 0.00147`，
关节 `7:36` 最大偏差 `0.05725 rad`、平均 `0.012752 rad`），未修复时骨盆只有 `0.4024–0.4967 m`。

---

## 三 Kimodo 生成的两段参考动作

### 3.1 提示词与产物

| 用途 | 探针 | 提示词 | 转换后 stem | 帧数 @25fps |
|---|---|---|---|---|
| 右臂靠近方块 | `p6` | *"A person stands and moves their right hand forward at waist height."* | `kimodo_conv/p6_conv` | 75（3.0 s） |
| 右臂抬升 | `l1` | *"A person stands still and raises their right hand up high in front of them."* | `kimodo_conv/l1_conv` | 75（3.0 s） |

片段哈希（`wb_kimo_p6l1` 运行时 harness 实际加载的值，与 `result.json.source` 一致）：

```
p6_conv.npz  ef46c0c22135d34de3a6cdd03e9f8b878e2d5e9353572b88fbc1c6b3f77b0ed1
p6_conv.csv  cbd727a264fbc46e530001466cc228ae3f7f9fed3978215820d26a53091cccff   (= result.source.paired_csv_sha256)
l1_conv.npz  2e9f38ef68c07f8125c222144b5a705f6d3d8826083cd63daa676d0b2894f3df
l1_conv.csv  d28991db7166132e521d16f981d85896b0cb6620683fc78c87fdbee3793d621b
```

### 3.2 转换：Kimodo(G1Skeleton34, 30fps) → harness 运动契约(25fps)
`rep/kimo2harness.py`：对 `local_rot_mats` 做 30→25 fps **slerp + SVD 正交化**，root 线性插值，
CSV 由 harness **自己的** `motion_input.convert()` 产出，因此对齐是构造精确的：

```
VERIFY ArdyMotion OK  parity joint≈5e-09  root≈5e-10  rot≈1e-09
```

### 3.3 候选筛选（闭环前的可解释筛选，不是事后挑数据）
harness 在 `APPROACH` 相位只在**片段的前 2 秒**采样先验（`t-2)/10`），而官方被接受的 `near_s42`
是一个**右臂包络极小**的片段（关节行程 `0.14–1.22 rad`）。以此为准做了 6 个 Kimodo 靠近候选的度量：

| 候选 | 提示词要点 | 与 `near_s42` 前 2 s 右臂 RMS (rad) |
|---|---|---|
| **p6** | 腰高向前 → **选中** | **0.766** |
| p1 | 胸高前伸 | 0.871 |
| p2 | 直立前伸 | 0.884 |
| p4 | 抬臂向前 | 1.171 |
| p5 | 抬到肩高 | 1.193 |
| p3 | 手放到桌上 | 1.208 |

抬升候选同样筛选（对照官方 `lift_s42`）：`l1` RMS 1.318 最优 → `l1`、`l5`、`l2`、`l3`、`l4`。
`p6`、`l1` 均**首次运行即通过**。

---

## 四 抓取时刻的程序控制（手臂位置 / 手腕转向 / 手指）

全部由官方 SONIC 控制器在既有相位机内执行，本任务不改物理代码：

- **手指在靠近之前张开**：`SETTLE/APPROACH/PREGRASP/DESCEND/ALIGN` 相位的指令参考
  **逐帧恰好等于 `core.OPEN`**（`[0, -0.7, -2.0, 1.4, 0.08, 1.4, 0.08] rad`），共 **1116 帧**；
  实测关节最大偏差 **0.0106 rad（0.61°）**（力矩控制器的跟踪残差）。
- **抓取**：`DESCEND/ALIGN` 把闭爪掌心目标插值到方块面心（`pinch_geometry`，`highpos = 方块中心 + [0,0,0.10]`），
  `CLOSE` 在 `close_seconds = 0.5 s` 内按 `blend(OPEN, close_hand)` 闭合，`close_hand[2] = -0.88`。
- **手腕转向**：`CLOSE` → `LIFT` 之间腕部姿态变化 **3.22°**（基本冻结）。
- **抓住之后手指保持不变**：`HOLD` 相位相对首帧漂移 **9.24e-05 rad**；`LIFT+HOLD` 全程最大
  绝对变化 **0.00500 rad**，单步最大 **2.07e-04 rad**（即"抓住后保持不变"）。

---

## 五 闭环验证结果（`wb_kimo_p6l1`）

### 5.1 相位事件

| 相位 | 时刻 (s) |
|---|---|
| SETTLE | 0.000 |
| APPROACH | 2.002 |
| PREGRASP | 24.408 |
| DESCEND | 36.410 |
| ALIGN | 44.412 |
| CLOSE | 44.612 |
| LIFT | 45.554 |
| HOLD | 53.558 |
| RELEASE | 55.562 |
| SETTLE_RELEASE | 56.566 |

### 5.2 20/20 门

`completed, hold_7cm, two_fingers, no_support, clearance_4cm, slip_1cm, release_drop_6cm,
final_supported, final_fingers_off, no_external, no_warnings, upright, no_table_rest_in_hold,
no_nonfoot_floor_support_in_hold, feet_supported_in_hold, fingertip_only_robot_contacts_in_hold,
final_table_supported, actual_arm_speed_within_limit, actual_body_limits_within_2mrad,
no_robot_table_contact_full_task` —— **全部 `true`**，`fail = null`。

### 5.3 关键量

| 指标 | 值 |
|---|---|
| 方块举升高度 | **0.1441 m**（闭合时 0.77441 m → 峰值 0.91849 m） |
| 抬升段落地回位 | 最终 0.77441 m |
| 抓取时刻腕部位置 | `[0.27725, -0.06899, 0.94345] m`；相对方块 `[+0.0103, +0.0490, +0.1690] m` |
| 最大指面接触力 | 拇指 2.504 N / 中指 2.503 N |
| 支撑面捕获误差峰值 | 0.2238 m（瞬态，最终收敛） |
| 指面竖直展开峰值 | 0.0533 m（瞬态） |
| 底座水平漂移峰值 | 0.0391 m |
| 实际手臂最大速度 | 1.348 rad/s（门限 2.0） |
| 身体关节超限 | 0.0 rad（门限 2 mrad） |
| `state_mutations` / `control_mutations` | `false` / `false`（无作弊） |
| `ardy_arm_prior_consumed_by_sonic` | `true` |
| `native_path_consumed_by_sonic` | `true` |
| 分支静力搜素 | 7 候选全部评估，选中 `arm_nullspace_basis01_step-010`，静态捕获误差 `1.97e-15 m`，指部重规划误差 `0.736 mm`，臂限位余量 `0.0541 rad` |

### 5.4 状态机诊断（本次工作的方法学副产品）
用**纯日志副本**（`rep/dbg_grasp.py` / `dbg2_grasp.py`，不改官方文件，其 sha256 前后一致）定位过两类失败：

1. `ValueError: Approach clock bound0..26s`：`clearance_approach.update` 硬编码 26 s 上限，
   而 `APPROACH` 只有在 `elapsed ≥ passed_time + 6 s` 且爪心距 `highpos` < 2.5 cm 时才切 `PREGRASP`，
   因此**腕部必须在 elapsed ≤ 20 s 前越过 0.90 m**。官方基线与 `p6_conv` 都在 **e≈15.56 s** 越过，余量充足。
2. 早期 Kimodo 候选（如 `p4_conv`）虽同样在 e≈15.56 越过，但 `clearance_passed` 之后
   `BranchExecution` 会把参考强行指向分支目标；若该跳变对 C2 参考滤波器不可行，
   `--reference-fallback` 会**继续执行上一段已认证轨迹**，手臂于是继续跟随"抬臂"先验而非抓取位姿，
   爪心误差停在 0.088 m（门限 0.025 m）而超时。因此**先验片段的右臂轨迹必须与任务位形相容**——
   这正是 §3.3 的筛选依据。

---

## 六 交付物

目录：`/data/group4/20261008-232029-workbuddy-34e89f61/wb_deliverable/`

| 文件 | 说明 |
|---|---|
| `g1-rightcube-grasp-kimodo-30fps.csv` | **主交付**：1788 行 × 51 列，30 fps，t = 0…59.567 s |
| `g1-rightcube-grasp-kimodo-30fps.json` | 导出元数据（相位区间、`root_fixed` / `quat_fixed`、列名） |
| `g1-rightcube-grasp-harness-result.json` | harness 判定（20 门、事件、来源哈希） |
| `g1-rightcube-grasp-verify.json` | 抓取控制验证（手指开合、冻结漂移、腕部几何、举升） |
| `kimodo-reach-p6_conv.{npz,csv}` | 靠近段 Kimodo 片段（可复现输入） |
| `kimodo-lift-l1_conv.{npz,csv}` | 抬升段 Kimodo 片段（可复现输入） |

CSV 契约：

```
t_s, root_x, root_y, root_z, quat_w, quat_x, quat_y, quat_z,
left_hip_pitch_joint … right_wrist_yaw_joint, right_hand_thumb_0_joint … right_hand_middle_1_joint
```
- `root` 列在 1788 帧上**只有一个取值** `[0, 0, 0.7887]`；
- 四元数列**只有一个取值** `[1, 0, 0, 0]`（wxyz）；
- 共 43 个具名关节，顺序与 MuJoCo XML 铰链顺序一致。

---

## 七 复现步骤

```bash
# 0) 环境
source /home/group4/group4_dasc7606c/work/kimodo/env.sh          # MUSA_VISIBLE_DEVICES=5, kimodo venv

# 1) Kimodo 生成（带 MUSA 注意力补丁 + 文本编码器进程内修复）
D=/data/group4/20261008-232029-workbuddy-34e89f61
W=/home/group4/group4_dasc7606c/work/20261008-232029-workbuddy-34e89f61/workbuddy
bash $W/scripts/gen_fix_cli.sh ...        # 见 kimodo_logs/ 的实际调用
#    靠近: "A person stands and moves their right hand forward at waist height."
#    抬升: "A person stands still and raises their right hand up high in front of them."

# 2) 转 harness 25fps 契约
cd $D/harness_s1000/rep && python -B kimo2harness.py \
    --npz $D/reach_probe/p6.npz --stem $D/kimodo_conv/p6_conv --fps 25
cd $D/harness_s1000/rep && python -B kimo2harness.py \
    --npz $D/lift_probe/l1.npz  --stem $D/kimodo_conv/l1_conv  --fps 25

# 3) 闭环执行 + 30fps 导出
bash $D/wb_loop3.sh p6_conv l1_conv wb_kimo_p6l1

# 4) 抓取控制验证
WB_REP=$D/harness_s1000/rep python $W/scripts/wb_grasp_control.py wb_kimo_p6l1
```

---

## 八 边界与遗留

1. `clearance_approach.py` 的 26 s 硬上限与 `BranchExecution.approach_timeout_seconds = 32` 不一致
   （第 300 行的超时判定永远不会生效，因为第 328 行先抛异常）。本任务两次运行都在 22.5 s 内完成 APPROACH，
   **未触发**；但这是一个值得反馈给 SONIC 侧的潜在缺陷。
2. 共享仓 `repos/kimodo` 目前仍带着他人任务的未提交改动（Mistral 预设）。
   本任务在**进程内**规避，**未改动任何共享文件**；按 `reports/20261006-145744-qoder-169a1759-report.md`
   的既有结论，**回退才是干净解**，这需要仓主决策。
3. 抓取后的 `RELEASE/SETTLE_RELEASE` 会把方块放回桌面（官方任务定义的完整流程），
   因此 CSV 中举升是中间段而非结尾；举升峰值高度见 §5.3。

---

## 附录 R：SONIC 环境仿真出图（2026-10-09 02:1x）

出图完整复用 SONIC 侧已建好的仿真资产，**未新建任何环境**：

| 项 | 来源（SONIC 侧既有） |
|---|---|
| MuJoCo 模型 | SONIC 仿真 run 落盘的 `harness_s1000/rep/out/wb_kimo_p6l1/scene.xml`（sha `c6d188a8…`）+ `g1_free_grasp.xml`（sha `bd0743ce…`） |
| 状态轨迹 | 同一 run 的 `trajectory.npz`（sha `4e66c294…`，`qpos (1490,57)`，`fps=25`） |
| 渲染后端 | 节点上既有的 OSMesa 探针库（`MUJOCO_GL=osmesa`），**非新装** |
| 渲染器 | 本任务自写 `wb_render_sonic.py`（只读 SONIC 产物，不产生动力学） |

即：**动力学由 SONIC 的 MuJoCo 跑出，渲染只做回放成像**。

### 关键帧读数（来自 trajectory.npz 逐帧）

```
PREGRASP t=24.44  cube_z=0.7744  rise=-0.1mm  right-hand/cube contacts=0
DESCEND  t=36.44  cube_z=0.7744  rise=-0.1mm  contacts=0
ALIGN    t=44.44  cube_z=0.7744  rise=-0.1mm  contacts=0
CLOSE    t=45.08  cube_z=0.7744  rise=-0.1mm  contacts=0
LIFT     t=49.52  cube_z=0.8223  rise=+47.7mm contacts=2
HOLD     t=54.84  cube_z=0.9184  rise=+144.0mm contacts=2
```

### 图件清单

| 文件 | 内容 |
|---|---|
| `g1-rightcube-sim-sheet-grasp-sequence.png` | **主图**：抓取决定性 6 帧（PREGRASP→DESCEND→ALIGN→CLOSE→LIFT→HOLD）近景拼版 |
| `g1-rightcube-sim-sheet-focus.png` | 12 帧近景全流程 |
| `g1-rightcube-sim-sheet-top.png` | 12 帧俯视全流程 |
| `g1-rightcube-sim-sheet-landmarks.png` | 21 帧关键相位拼版 |
| `g1-rightcube-sim-sheet-strip.png` / `-strip-closeup.png` | 均匀采样长条（全程/近景） |
| `g1-rightcube-sim-motion.gif` / `-motion-closeup.gif` | 逐帧动画（GIF） |
| `g1-rightcube-sim-frame-close-t4464.png` | 单帧：CLOSE t=44.64 |
| `g1-rightcube-sim-frame-lift-t4952.png` | 单帧：LIFT t=49.52（rise +47.8mm） |
| `g1-rightcube-sim-frame-hold-t5484.png` | 单帧：HOLD t=54.84（rise +144.0mm，接触=2） |
| `g1-rightcube-sim-bridge-offscreen-sheet.png` | 对照组：SONIC 官方 `run_grasp.py --offscreen` 自己渲染的画面（11 帧） |

### 复现

```bash
bash $B/work/$T/workbuddy/scripts/wb_render_run.sh \
  $B/work/$T/harness_s1000/rep/out/wb_kimo_p6l1 \
  /data/group4/$T/sonic_bridge_replay/renders_grasp2
```

---

## 附录 V：仿真视频（2026-10-09 03:00）

渲染链路与附录 R 完全相同（SONIC 的 `scene.xml` + `g1_free_grasp.xml` + `trajectory.npz`，
OSMesa 软件 GL 回放），只是把逐帧图像交给 **节点自带的静态 ffmpeg 7.0.2**
（`envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2`，
只读执行）编码为 H.264。**不是抽帧加速**：全长视频为 stride 1 逐帧，1490 帧 ÷ 25 fps = 59.60 s。

| 文件 | 内容 | 时长 | 大小 |
| --- | --- | --- | --- |
| `g1-rightcube-sim-grasp-full.mp4` | 全程，SONIC 场景自带相机视角 | 59.60 s | 5.77 MB |
| `g1-rightcube-sim-grasp-closeup.mp4` | 全程，跟踪方块的近景 | 59.60 s | 9.50 MB |
| `g1-rightcube-sim-grasp-decisive.mp4` | t=43.2–56.8 s，近景 | 13.64 s | 3.32 MB |
| `g1-rightcube-sim-grasp-decisive-wide.mp4` | t=43.2–56.8 s，宽视角 | 13.64 s | 1.48 MB |

规格统一：`h264 (High) / yuv420p / 960x720 / 25 fps / SAR 1:1 / CRF 18 / +faststart`。

视频中的关键读数（逐帧前向运动学，基准 `cube_z₀ = 0.7744 m`）：

```
DESCEND t=43.22s  rise   -0.1mm  contacts=0
CLOSE   t=44.90s  rise   -0.1mm  contacts=0
LIFT    t=46.58s  rise  +51.4mm  contacts=2   >>> GRASPED
LIFT    t=49.94s  rise +135.4mm  contacts=2
LIFT    t=53.28s  rise +152.2mm  contacts=2
HOLD    t=54.96s  rise +152.7mm  contacts=2
SETTLE_RELEASE t=56.64s rise -0.1mm contacts=0   （方块放回桌面）
```

扫描帧序列保留在 `sonic_bridge_replay/video_frames/{main,side}/`（各 1490 帧，共 328 MB），
可按不同参数重编码而不必重渲。

复现：
```bash
T=20261008-232029-workbuddy-34e89f61; B=/home/group4/group4_dasc7606c
setsid nohup nice -n 19 bash $B/work/$T/workbuddy/scripts/wb_render_video_run.sh \
  > /data/group4/$T/sonic_bridge_replay/video.log 2>&1 < /dev/null &
```
