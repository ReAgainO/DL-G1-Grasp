# MIGRATION.md — 公开方案可迁移件对照表（ws3_static）
- 父 TASKID: 20261008-221515-qoder-03c4673f；节点 worker00039；性质：纯读 + clone，静态提炼（本节点为 MUSA GPU，无 CUDA，Isaac 系不可实跑）
- 沙盒: /data/group4/20261008-221515-qoder-03c4673f/ws3_static/repos/
- 本组现状数字出处一律给路径；"本组"= unitree G1+Dex3 + MuJoCo 3.2.7 + SONIC 抓取线
- 尺寸曲线基线（父会话口径的权威出处）: /home/group4/group4_dasc7606c/reports/20261008-125638-qoder-d266d3a9-report.md:12
  "20 mm 0/250、25 mm 4/150（2.7 %）、35 mm 255/392（65.1 %）、50 mm 60/96（62.5 %）"（非单调）
  同源补充: reports/20261008-214754-codex-1ac8adb9-report.md:24（20mm：8mm 切向半宽可抬升 91–108mm，HOLD 前失持）

---

## M1【高】usl Dex3 手指位置伺服配方（kp=100 / kd=10 / armature=0.1）与"手指并入全身位置动作空间"的对照
- 来源与版本: unitreerobotics/unitree_sim_isaaclab @ e30c25b1dffdf92ada1d6c8c1fe9a47bdde0fecc
  - robots/unitree.py:154-171（hands ImplicitActuatorCfg：joint_names_expr .*_hand_{index,middle,thumb}_.*_joint；effort_limit=300；velocity_limit=100；stiffness=100.0；damping=10.0；armature=0.1）
  - tasks/g1_tasks/pick_place_redblock_g1_29dof_dex3/pickplace_redblock_g1_29dof_dex3_joint_env_cfg.py:60（动作 = JointPositionAction(joint_names=[".*"])，手指 14 关节并入同一位置空间）
- 是什么: 官方 Dex3 抓取任务里，手指是"高刚度位置伺服"（kp=100/kd=10）并带 armature 0.1；整个 43 关节（29body+14hand）共用一个位置动作空间，不区分"body 通道 / 手指通道"
- 本组现状对照:
  - 手指是纯力矩通道：work/20261006-093203-codex-6385a841/finger_control.py:5-21（PD 误差乘 kp/kd 后 clip 到 ctrlrange 输出力矩）；sonic_grasp.py:412 d.ctrl[hands]=finger_torques(...)
  - 场景手指力矩上限低：repos/sonic-bridge/g1/g1_29dof_with_hand.xml:603-609 ctrlrange 拇指 0 ±2.45、其余 ±0.7（官方 HF 版是 ±1.4，低一半，见 M3）
  - 机制结论已有：reports/open-issues.md:501 "力与摩擦都不是瓶颈……mu 从 1.0 扫到 2.5 零改善；tau 2.0 N·m 远超需求 0.028 N·m"——所以本件的目的不是"加力"，而是换控制系统结构做消歧
- 缺失项: 本组从未试过同等量级的位置伺服（100/10）+ armature 注入；失败被归因"包围构型"（open-issues.md:525），但"构型下的指端刚度/瞬态"未与此配方分离过
- 落地成本: 2-4 小时
- 预期收益: 用一次 35mm 阳性对照 + 一次 20/25mm 层，即可判定"低刚度力矩通道"是否在包围构型已成立时仍吃成功率；若 35mm 阳性提升，则 20/25mm 层同配方直接复用（对应 2.7%→? 的快速试探）
- 建议动作:
  1. 在 finger_control.py 旁新增位置模式包装（不改原函数默认行为）：`hand_cmd = clip(kp_pos*(q_target-q) - kd_pos*qd, ctrlrange)`，参数起点 kp_pos=100, kd_pos=10
  2. 在 sonic_grasp.py:412 处用开关 `--finger-pd 100,10` 切换；模型 XML 侧把手指 actuator 增加 armature=0.1（只动 g1_29dof_with_hand.xml 的手指段，先在副本上做）
  3. 跑批：35mm 场景 3 格阴性/阳性对照（`a35_02_05` 等既有格名），再 c20f/d25 层各 6 格；判据沿用 fixE_tally.csv 的列

## M2【高】usl 物理配方翻译到 MuJoCo（小方块 0/250 的物理闸门排查）
- 来源与版本: 同上 @ e30c25b1
  - env_cfg:145-163（decimation=2、episode 20s、sim.dt=0.005、enable_ccd=True、num_substeps=4、contact_offset=0.01、rest_offset=0.001、friction_correlation_distance=0.003、num_position_iterations=16、num_velocity_iterations=4、bounce_threshold_velocity=0.01）
  - common_scene/base_scene_pickplace_redblock.py:52-74（方块 0.06³ m、mass 1.0、static_friction=10、dynamic_friction=1.5、restitution=0.01、contact_offset=0.01/rest 0.0）
- 是什么: 官方给小方块/小物体的仿真配方=高频子步 + 低弹跳阈值 + 稳定接触（大迭代次数、摩擦相关距离）+ CCD
- 本组现状对照:
  - 本组方块更小：repos/sonic-bridge/g1/scene_grasp_hand.xml:49-57 cube 半宽 0.0175（=35mm）且 20-25mm 层是同等几何继续缩小（报告 125638 尺寸曲线）
  - 本组已改方块碰撞位掩码：work/20261006-093203-codex-6385a841/source_physics_core.py:111-114（contype=1/conaffinity=3）
  - MuJoCo 没有 enable_ccd 开关；等价物是 timestep 细分、geom margin 与 solref 时间常数、impratio——需要逐项翻译，不能照抄
- 缺失项: 本组没有对"更小方块"档做过 substep/margin/solref 的敏感性扫描；20mm 层 0/250 是否含穿透/漏接触假失败未知
- 落地成本: 2-3 小时（脚本化扫描）
- 预期收益: 若 20mm 层部分失败是数值性（穿透/接触丢失），可把 0/250 从"机制失败"中剥离出来；直接改善对 20/25mm 假失败率的信任度（当前 25mm 2.7% 分母 150）
- 建议动作: 在 source_physics_core.prepare_model 增量加参数（不改默认）：`--substep 4`（dt 0.005/4）、`--contact-margin 0.001`、`--solref 0.02 1`、`--impratio 10`，先在 25mm 层的 10 格做 A/B，判据看 fixE_tally 的 slip_mm 与 two-finger contact timeout 计数

## M3【中】HF lerobot/unitree-g1-mujoco 官方 Dex3 档位与本组差异（力矩上限、腕相机几何、通道拆分）
- 来源与版本:
  - huggingface/lerobot @ b863b4228356dc53db25d097f2404e4f02a60834：src/lerobot/robots/unitree_g1/controllers/sonic_whole_body.py:17-29（两套关节序）、:53-65、:157-218（SONIC decoder-only，输出仅 29 关节 <joint>.q）；config_unitree_g1.py:24-35、:64（end_effector 支持 dex3）；envs/configs.py:730-775
  - HF 仓 lerobot/unitree-g1-mujoco @ 68459ed68f6f68e1f661091dfcb6ebce44681aec：README（dex3=assets/scene_hands_cameras.xml、nq=50/nu=43、腕相机 95° vFOV、ZMQ 5555）；assets/g1_29dof_with_hand_cameras.xml 手指 <motor> ctrlrange 拇指0 ±2.45、其余 ±1.4；default class finger_motor damping .05/armature .01/frictionloss .1
- 是什么: 官方 MuJoCo 版把"SONIC 只驱动 29 body + 手指单独物理通道"写死为架构事实（与本组结构相同），并给出官方手指力矩档位与腕相机参数
- 本组现状对照:
  - 本组手指 ctrlrange ±0.7（repos/sonic-bridge/g1/g1_29dof_with_hand.xml:603-609）= 官方一半；本组也复用了"SONIC 独立手指通道"结构（sonic_grasp.py:154,412）
  - 腕相机：open-issues.md:90 `ISS-SONIC-BRIDGE-FOVY-45-NOT-42`（手算需更正 fovy45/fy869/顶面 12.6px）；官方 dex3 腕相机 vFOV 95°、640x480
- 缺失项: 未做官方档位（±1.4/±2.45）与本组 ±0.7 的对照；腕相机几何更正未落到脚本
- 落地成本: 1 小时（力矩三档 A/B）+ 0.5 小时（fovy 修正进 grasp_camera 几何）
- 预期收益: 以官方档位为外部参照一次性消歧"限幅过低"假设（即便结论是"无关"，也把 20/25mm 层失败归因收窄）；腕相机修正直接服务落点精度门（`ISS-GRASP-DWELL-GATE-IS-LANDING-ACCURACY`，gap_at_close p50 13.0mm，成功格 1.8-8.3mm）
- 建议动作: 复制 HF 官方 XML 手指段到本地副本做 ctrlrange ∈ {±0.7, ±1.4, ±2.45} 三档；`grep -n fovy` 修正 sonic-bridge 相机几何脚本后重跑 3 格对照

## M4【中】HOMIE 自由基座下蹲课程 → free-base 抓取的"中间门"
- 来源与版本: InternRobotics/OpenHomie @ 33071f79f1884bb122bd45631c8c60d61dac1eb8
  - HomieRL/legged_gym/legged_gym/envs/g1/g1_29dof_config.py:118-130（commands 含 height，range [-0.5, 0]）；:204-251（tracking_base_height=2.0、base_height_target=0.74、clearance_height_target=0.14、only_positive_rewards=False）；:263（action_curriculum=True）
  - HomieRL/README.md（Upper-body Pose Curriculum / Height Reward / Symmetry）；根 README（arXiv:2502.13013；2026-07 note 指向 NVlabs/GR00T-WholeBodyControl 的 homie v2 policy 并建议直接用最新 SONIC）
- 是什么: 训练 G1 在"任意连续变化的上肢姿态"下走+下蹲的 RL 配方：高度命令跟踪是显式奖励项（r_height=2.0），课程逐步加难度
- 本组现状对照:
  - 本组 free-base 抓取 22/22 全灭且不是跌倒：open-issues.md:1539（`--free-base` 下 keyframe 与 IK 两路 0 接触，up_z_min 0.94-0.96）；open-issues.md:77 `ISS-FREEBASE-HAND-MISLOCATED`（拦路石在腕部绝对定位，不在手指层）
  - 本组是"全或无"判定，没有把"下蹲/基座高度到位"作为独立可测门
- 缺失项: free-base 实验缺少中间观测量（基座高度轨迹 vs 目标、下蹲深度的到达误差）
- 落地成本: 3-5 小时（评估层加门，不训 RL——MUSA 无 IsaacGym，只搬"度量与课程"思想）
- 预期收益: 把 free-base 全灭拆成"下蹲不到位 / 蹲到位但腕偏 / 腕到位但闭合失败"三段可归因；这是把 free-base 线从 0 变为"有梯度"的最低成本路径
- 建议动作: 在 sonic_grasp.py 的 free-base 跑批输出 JSON 里增记 `base_height_series`、`squat_target_series` 与到达误差 p50；判据先只观察不设门；对照 HOMIE 课程思想做"目标蹲深 0.74→0.70→0.66"的梯度扫描

## M5【中】xrteleop / il_lerobot 的 Dex3 遥操与示范数据通道（手指 action 的"数据驱动"来源）
- 来源与版本:
  - unitreerobotics/xr_teleoperate @ 817fb00c63cde15e5f24a0f8fa08e1e33ed89d3b：teleop/robot_control/robot_hand_unitree.py:27-31（7 电机、DDS 话题 rt/dex3/{left,right}/{cmd,state}）、:141-148（手 PD kp=1.5/kd=0.2）、:199-203（14 维 state/action 数组）、:213-229（左右手关节序不同：右手 index/middle 互换）；hand_retargeting.py:50-59（dex3 API 关节名→硬件序映射，依赖 dex_retargeting 库与 unitree_dex3.yml）；teleop_hand_and_arm.py:76（30Hz 录制）、:90-95（task json：task-name/goal/desc/steps，例 "pick cube" / "pick up cube."）
  - unitreerobotics/unitree_IL_lerobot @ 41c2805742de879ddab2d8d6beaeaf215f876395：eval_robot/robot_control/robot_hand_unitree.py:1-160（与 xrteleop 同源的 Dex3 控制器）；eval_g1.py:119-125（state=arm_dof+2*ee_dof）、:140-147（action 拆分：arm→IK；左右手各 ee_dof→手控制器）；utils/episode_writer.py:17,121-133（data.json 的 states/actions，30Hz）
- 是什么: 官方 Dex3 的"人类示范→重定向→14 维手指目标"完整链路，以及 IL 数据里手指与臂并列进 state/action 的字段约定
- 本组现状对照:
  - 本组手指目标来自手工 blend：sonic_grasp.py:401-412（OPEN/closed 关键帧 + AdaptiveHand 速率限制 3e-3/tick）
  - 已知坑：reports/open-issues.md:132 `ISS-KIMODO-CSV-NO-FINGER-CHANNEL`（KIMODO G1 36 列导出无手指通道——任何改手指时序的活落空）；:133 NPZ/CSV 骨架不一致
- 缺失项: 本组没有"人类示范手指轨迹"通道；手指时序是调参对象而非数据对象
- 落地成本: 2-4 小时（数据格式适配；dex_retargeting 依赖 pypi/gitee 可达性需先验证——huggingface.co 不通、gitee 可用）
- 预期收益: 手指闭合轨迹可换为示范驱动，直接服务 20mm 层"8mm 切向半宽可抬升但 HOLD 前失持"（125638 报告附录）的时序问题；也是 ARDY→SONIC 不动手指通道缺口的现成补丁
- 建议动作: 采 1 条 30Hz 示范（或复用 xrteleop data.json）→ 提取 14 维 action → 在 AdaptiveHand 处加 `--hand-ref <json>` 通道回放；先做 35mm 阳性对照

## M6【低-中】usl 任务设计逐项表（判据/观测/位置域/相机）作为本组对照与 place 段参照
- 来源与版本: 同上 @ e30c25b1（证据行号见 [04] 段）
- 是什么/逐项表:
  | 项 | usl 取值（行号） | 本组对照（路径） |
  |---|---|---|
  | 方块 | 60mm 立方 mass1.0 摩擦 10/1.5（base_scene:52-74） | 35mm 半宽 0.0175（sonic-bridge g1/scene_grasp_hand.xml:55-57）；20/25mm 变体见 125638 报告 |
  | 成功/判据 | 工作区外→reset（base_termination:15-38）；post 窗口 reward（base_reward:56-62,87-98，x±18.5mm y±24mm h 0.82-0.825） | 20 道 gates + result.json（fixE_tally.csv；FINDING.md） |
  | 位置域 | reset x/y ±5cm（env_cfg:107-121） | 厘米级（open-issues.md:111 `ISS-GRASP-REACH-DOMAIN-CM-SCALE`）——同为厘米级，官方不靠加密域 |
  | 观测 | 关节态+dex3 手态 14 维+三相机（env_cfg:64-93；dex3_state.py:31-50,111） | sonic_grasp 内部观测量（见 FINDING/rep） |
  | 相机 | front + 左右腕 640x480 f12（camera_configs.py:87-173） | grasp_camera（fovy 需更正，open-issues.md:90） |
  | 控制 | JointPositionAction 全关节 100Hz（env_cfg:60,145-148） | SONIC 50Hz body + 手指力矩（sonic_grasp.py:396,412） |
- 本组现状对照/缺失项: PLACE 段没有量化的目标窗口（本组门多为"抬升/滑移/支撑"类，落点类门 gap p50 13mm 来自 `ISS-GRASP-DWELL-GATE-IS-LANDING-ACCURACY`）
- 落地成本: 1-2 小时（如要把 post 窗口方式写进 PLACE 段评估）
- 预期收益: 给 PLACE 段一个外部设计参照（目标柱窗口 ±2cm 级 + 5mm 高度带），把"落地精度"要求显式化
- 建议动作: 在评估脚本里为 PLACE 增加 `place_window` 报告项（照抄 post 窗口语义：x/y ±2cm、高度带 5mm），先只观察

## M7【N/A，记录用】usl 四段流程中"合成增强（改光照/相机重拍）"不迁移
- 来源: usl README.md:230-250（--generate_data/--generate_data_dir/--modify_light/--modify_camera）
- 不迁移原因: 依赖 Isaac Sim 渲染管线；本节点 MUSA 无 CUDA，Isaac Sim/Lab 无法实跑（任务背景明示）。MuJoCo 侧替代（mjv 多光照渲染）存在但与本组数据现状（无视觉策略在环）不匹配
- 成本: 0（记录）；收益: 0（当前线不用）

---

## Top-3 摘要（供回传）
1. M1 usl 手指位置伺服配方（kp100/kd10/armature0.1）——与"包围构型"主线协同，2-4h，能一次分离"执行通道 vs 构型"因子
2. M2 usl 物理配方 MuJoCo 翻译（substep/margin/solref/impratio）——20mm 0/250 的假失败排查，2-3h
3. M4 HOMIE 下蹲课程→free-base 中间门——把 free-base 22/22 全灭拆成可归因梯度，3-5h

## 附：引用纪律
- 20/25/35/50mm 数字引用必须带 `reports/20261008-125638-qoder-d266d3a9-report.md:12` 或 `reports/20261008-214754-codex-1ac8adb9-report.md:24`（两者同源同口径）
- 机制结论引用 `reports/open-issues.md:501/525/628/1539`（禁把 mu/力矩当主因）
- DexUMI/GEX 禁引条款见 SEARCH-NOTES.md
