# FINDING — menagerie G1（带三指手）桌面方块抓取复现（ws1, TASKID=20261008-221515-qoder-03c4673f）

## 结论（3 行）
1. **复现失败**：本协议下 mujoco_menagerie `unitree_g1/g1_with_hands.xml`（官方 sha256=2d41a3c6…，35,285B）三指手对 20/25/35mm 方块的真实抓取成功率 **0/45**（资产原增益 kp=500 0/30，kp=100 变体 0/15）；失败点高度一致：t=1.3s 夹具释放瞬间方块即脱手，抬升恒 0（release_slip 6-7cm）。
2. **测试链路有效**（§5A.2 分支验证）：理想固连正对照（harness self-test）e20/e25 各 2/2 成功（lift 0.26/0.29m、slip=0、接触占比 0.999、fi≈14/21N），e35 正对照 lift 0.16m+slip=0 达标但指接触门 0/2；负对照（手指不闭合）9/9 如期失败。⇒ 失败在抓取物理，不在评测链。
3. **根因（实测）**：该手三指尖固定高差（index 恒高于 middle 57mm 中心距、thumb 居中）使所有捏合退化为上下面夹持/楔形接触；释放瞬间楔形+点接触存不住方块；叠加资产 README 自陈的增益问题（kp=500 位置伺服、1.4Nm 限幅）。kmu=1 默认摩擦、指尖无专用垫。

## 结果表（n/success，success_table.csv 为准）
| 尺寸 | grasp(资产 kp500) | grasp(kp100) | negctl | ideal 正对照 |
|---|---|---|---|---|
| 20mm | 0/10 | 0/5 | 0/3 | 2/2 ✓ |
| 25mm | 0/10 | 0/5 | 0/3 | 2/2 ✓ |
| 35mm | 0/10 | 0/5 | 0/3 | 0/2（lift✓ slip✓ contact✗）|

判据列明细（lift_final/lift_max/slip/contact_any/contact_frac/fi_max/weld_free…)见 success_table.csv；每行另有 runtime_stamp（mujoco_version=3.2.7、sys_executable、python 3.10.22、model_sha=2d41a3c6…、dt=0.002）。

## 负对照结果（必须失败）
- negctl 9/9 失败：手指全程保持在张开构型（ctrl=O7，λ=0），夹具释放后方块自由落体至桌面（lift_final=0、slip 0.18-0.21m、contact_any=0）⇒ 满足"手指不闭合必须失败"。
- 正对照（ideal，标注为 harness self-test 而非真实抓取）：20/25 档 2/2 全判据通过，证明成功分支可达；35 档抬升/滑移达标但指-块接触力恒 0（0/2），说明 35mm 档在当前标定下连固连状态都测不到指接触。

## 手型号核实（关节名清单 / 几指几关节 / 与 Unitree Dex3 异同）
- 资产每手 **3 指 7 关节**；右手指关节实测清单（g1_with_hands.xml，含轴/行程）：
  - `right_hand_thumb_0_joint` axis(0,1,0) ±1.0472（拇指根部外展）；`right_hand_thumb_1_joint` axis(0,0,1) [-1.0472, 0.7243]；`right_hand_thumb_2_joint` axis(0,0,1) [-1.7453, 0]；
  - `right_hand_middle_0_joint` axis(0,0,1) [0, 1.5708]；`right_hand_middle_1_joint` [0, 1.7453]；
  - `right_hand_index_0_joint` [0, 1.5708]；`right_hand_index_1_joint` [0, 1.7453]。左手同构镜像（thumb_1/2、index/middle 符号翻转）。
  - 骨架上 index 与 middle 的基座相差 ±28.5mm（z 向），thumb 居中间层；三指尖 z 恒定分离（index 平面 ≈+28.5mm、middle ≈−28.5mm）——这是失败机制的几何源头。
- **与 Unitree Dex3-1 对比**：官方 Dex3-1（G1 可选三指力控灵巧手）规格为"三指、7 自由度（拇指×3、食指×2、中指×2）、最大力矩 3.1 N·m"——指型/关节数与实测模型**一致** ⇒ 该手即 Dex3-1 三指手（model 名 g1_29dof_with_hand_rev_1_0，来源 unitree_ros g1_description）。
  - **异**：① 资产关节力矩限幅 1.4 N·m（thumb_0 2.45）低于官方 3.1 N·m；② 资产手部执行器为位置伺服 kp=500/dampratio=1，README 自陈 "needs tuning"（本组历史记录官方控制器为 kp100/kd10）；③ 碰撞几何=连杆 STL 凸包，无指尖橡胶垫/球（本组自研件有 r=10mm 指尖球 μ=2.0）；④ 本资产无触觉传感建模。

## 失败机制证据（每一条均为实测）
1. **夹具释放即脱手**：30/30 grasp 的 release_slip（释放后 0.8s 纯指持阶段内方块相对手掌位移）6-7cm；释放后 30ms 内方块进入自由落体（逐 2ms 轨迹：cz 0.8725→0.8665，接触力衰减到 0；e20_grasp_000_traj.npz）。
2. **手指跟踪滞后**：闭合指令到 λ=0.55 时实际关节位置折算 λ≈0.377（逐 2ms 日志，thumb_1 qpos 折算），接触力仅 0.2-2.7N（远低于限幅 1.4Nm/力臂≈35N），未能形成可靠力闭合。
3. **静态审计口径 ≠ 仿真接触口径**：mk_geomDistance(mesh) 首次接触发生在 λ≈0.49-0.52，而仿真中 HULL 接触 ≈0.34 出现（凸包 vs 面网格差异），导致"平衡点"标定的 2mm 侧隙在动态中不复存在；这是本任务"不能只看接触计数"坑的一个新实例（几何距离口径也要钉死）。
4. **几何性：无对置侧夹**：open→close 扫描（closure_curve.json，101 档）显示 ti/tm/im 三对指尖距分别 62→8mm、106→−27mm、61→27mm，指尖逐档 z 分离不变（index≈0.914、thumb 0.858-0.889、middle 0.86），任何 λ 下都无法形成"左右对置 + 高度匹配"的平行侧夹；20/25mm 档的可行捏合是"上-下夹持"，35mm 档只能"上下顶住"。
5. **增益不是主因**：kp100 变体 15/15 仍全败（同失败签名），故排除"力矩太软"；资产原生 kp=500 的 1.4Nm 限幅则为固有问题（README 自陈需调）。
6. **与本组既有记录互证**：本组 10-08 记录"R3 成功件是 pads-only（指节是幽灵、只有 pad 承载）；开整只手后同一配置 20/20→7/20（指节顶开方块）"——menagerie 原装手恰是"整手碰撞全开（连杆凸包）"且无 pads 隔离，本实验 0/45 是该方向下的自然极端档，与"指节顶开方块"机制同源。

## 协议与偏离声明（如实）
- 方块初始置于"掌心预定抓取位"（静态审计无穿模，clr0=+0.2~+12mm），由临时 weld 夹具（`cube_holder`，world-cube）固定；闭合完成后、抬升前释放（"无 weld"判据=抬升期间 weld 非激活，全部运行满足）。
- 桌面（desk 顶 0.80m）仅作场景与落点，不接触手部（手最低向下扫掠 0.85m+）；曾试过"柱子/桌面承托方块"方案：实测手部闭合扫掠会深入方块底面以下 16-30mm（顶点云测绘），任何静态承托与手几何互斥，故改用悬浮+夹具方案（细节见 steps-ws1.md 第 [10]-[16] 条）。
- 方块 geom：friction=1 0.005 0.0001（资产默认）、condim=4、solref="0.004 1"（默认 0.02 太软，手指 35N 级接触力下穿入 ~15mm）。
- 矩阵扰动：初始位置 ±2mm 均匀扰动 + 审计门槛（spawn clearance ≥0.2mm，不足则重采样，最多 30 次）。

## 产物（绝对路径）
- `/data/group4/20261008-221515-qoder-03c4673f/ws1_menagerie/success_table.csv`（60 行，含判据明细）
- `.../ws1_menagerie/FINDING.md`（本文件）
- `.../ws1_menagerie/video/`：e20_grasp_0.mp4、e25_grasp_0.mp4、e35_grasp_0.mp4（失败例）、e20_negctl_0.mp4（负对照）、e20_ideal_0.mp4（正对照 self-test）；每段带 *_runtime_stamp.json + 关键帧 PNG
- `.../ws1_menagerie/out/runs/`（60 个 run JSON + traj.npz + log）、`out/probe/`（手结构/开合曲线/标定 placement）、`scripts/`（全部可复现脚本）、`model/unitree_g1/`（资产拷贝 + ws1_scene_model.xml 说明 + scene_model_record.json）
- 运行环境：mujoco 3.2.7（venv=/data/.../ws1_menagerie/env，uv 建），OMP=1，nice 10，并行 ≤12

## 加分项（未做，如实）
- lerobot/unitree-g1-mujoco 环境轻量评估：未执行（turn 预算耗尽于主线失败机理排查）。已知线索：HF 需走 hf-mirror.com；本任务未动。

## 下一步建议
1. 若要"能抓"，给该手换物理参数而非几何：指尖加 r≈10mm 球垫（condim=4，μ≈2.0）+ 手部 kp 降至 100/kv 匹配（本组自研件验证过的配方），并在 ≥40mm 方块上先验证对置侧夹。
2. 抓手几何：三指尖固定 57mm 高差决定"宽扁物体上下面夹持"才是本手舒适区；立方体 ≤35mm 建议改用两指+掌心托的 3 点托握姿（palm-up）研究，或改用 40-50mm 方块。
3. 评测链建议保留本次的 ideal/negctl 双对照设计（分支可达性 + 必须失败），它把"抓取 0/45"与"评测坏"明确区分开。
