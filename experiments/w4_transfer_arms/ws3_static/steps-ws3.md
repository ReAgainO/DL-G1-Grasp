# steps-ws3.md — 公开方案静态提炼（ws3_static）
- 父 TASKID: 20261008-221515-qoder-03c4673f；节点: worker00039
- 本机草稿: E:\qoder\qoder-data\Documents\Qoder\2026-10-08\2aa25fb2\worker-ws3\
- 远端流水: /home/group4/group4_dasc7606c/logs/20261008-221515-qoder-03c4673f/steps-ws3.md
- 沙盒: /data/group4/20261008-221515-qoder-03c4673f/ws3_static/repos/

## [01] 环境校验（2026-10-08 22:16 本地）
命令原文:
```
timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=10 S4000 'hostname; date "+%F %T"'
```
stdout:
```
worker00039
2026-10-08 22:16:40
```
stderr: (空)；退出码: 0。判定: 通过。
附: df -h → /data 11T avail；/home 4.7G avail（与背景一致）。沙盒 repos/ 已建 OK。

## [02] 只读盘点本组参照（确认路径存在）
- /data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/ 存在（FINDING.md 4.3KB、fixE_tally.csv 84 行）
- /data/group4/20261008-125638-qoder-d266d3a9/ 存在（S1000/raw 大量 result.json）
- /home/group4/group4_dasc7606c/repos/ 有 ardy, sonic, sonic-bridge, kimodo
- /home/group4/group4_dasc7606c/work/20261006-093203-codex-6385a841/ 有 sonic_grasp.py(611 行)、finger_control.py、source_physics_core.py 等

## [03] 五仓库 partial clone（22:18-22:30）
第一发普通 --depth 1 克隆 unitree_sim_isaaclab 超时（约 80KB/s，仓库含大量 USD/STL）；杀掉后改
`git clone --depth 1 --filter=blob:none --sparse`，再按需 `git sparse-checkout (add|set)`。全部成功。
commit sha（HEAD）:
- unitree_sim_isaaclab (usl)  e30c25b1dffdf92ada1d6c8c1fe9a47bdde0fecc
- lerobot                    b863b4228356dc53db25d097f2404e4f02a60834
- xr_teleoperate (xrteleop)  817fb00c63cde15e5f24a0f8fa08e1e33ed89d3b
- unitree_IL_lerobot (il_lerobot) 41c2805742de879ddab2d8d6beaeaf215f876395
- OpenHomie (openhomie)      33071f79f1884bb122bd45631c8c60d61dac1eb8
HF 仓 lerobot/unitree-g1-mujoco 无法 git clone（huggingface.co 不通），改 hf-mirror.com API/resolve 拉单文件。
revision: 68459ed68f6f68e1f661091dfcb6ebce44681aec（lastModified 2026-09-15）。

## [04] usl（unitree_sim_isaaclab）提炼要点（行号即证据）
- README.md:198-250 四段流程：2.4.2 遥操采集（配 xr_teleoperate）→ 2.4.3 回放（--replay --file_path）→ 2.4.4 合成增强（--generate_data 改光照/相机重拍）→ action_provider 提供策略动作接入（README:260 "policy-generated actions"，目录 action_provider/{dds,replay,...}）
- 任务：tasks/g1_tasks/pick_place_redblock_g1_29dof_dex3/*；env_cfg:43-50 机器人+三相机；:60 动作=JointPositionAction([".*"]) 全关节含手指
- 方块：common_scene/base_scene_pickplace_redblock.py:52-74 size 0.06³、mass 1.0、static_friction 10、dynamic_friction 1.5、restitution 0.01
- 判据：common_termination/base_termination_pick_place_redblock.py:15-38 工作区 x(-5.4,-2.9) y(-5.05,-2.8) h>0.5 外→reset；真"成功"在 common_rewards/base_reward_pickplace_redblock.py:56-62,87-98 post 窗口 x±18.5mm/y±24mm/h 0.82-0.825 → reward 1.0
- 位置域：env_cfg:107-121 reset pose_range x/y ±0.05（±5cm）
- 增益：robots/unitree.py:142-151 臂 kp 300/400/400 kd 3/2.5/2.5；:154-171 手 kp=100 kd=10 armature=0.1 effort 300 vel 100
- 物理：env_cfg:145-163（enable_ccd=True, substeps=4, contact_offset 0.01, rest_offset 0.001, num_position_iterations 16, num_velocity_iterations 4, friction_correlation_distance 0.003, bounce_threshold 0.01）
- 腕相机：common_config/camera_configs.py:143-173 dex3 腕相机 640x480 focal 12mm
- 手观测：common_observations/dex3_state.py:31-50 关节名表、:111 gather 索引 [31,37,41,30,36,29,35,34,40,42,33,39,32,38]

## [05] lerobot(GitHub)+HF lerobot/unitree-g1-mujoco 提炼要点
- robots/unitree_g1/config_unitree_g1.py:24-35 增益分组（arm kp 50/50/80/80 kd3；wrist 40/1.5）；:55 default_positions 29；:58 control_dt 1/250；:64 end_effector 默认 DEX1，支持 dex3
- controllers/sonic_whole_body.py:17-29 明示两套关节序（IsaacLab/MuJoCo）；:53-65 CONTROL_DT 0.02(50Hz)、TOKEN_DIM 64、HISTORY_LEN 10、DECODER_INPUT_DIM 994、权重 lerobot/sonic_decoder；:157-218 run_step 输出仅 29 关节 <joint>.q（手指不在该动作空间）
- robots/unitree_g1/unitree_g1.py:84-88 控制器只吃 (29,) kp/kd/default_angles；:295-298 无控制器时 action=29 关节；:250-269 publish_lowcmd 只遍历 G1_29_JointIndex
- envs/configs.py:730-775 G1EndEffector{DUMMY,DEX1,DEX3}；UnitreeG1MujocoEnv hub_path="lerobot/unitree-g1-mujoco"
- docs/source/unitree_g1.mdx:69,75 dex3 选择 MuJoCo 模型→决定手指 actuator 与腕相机
- HF 仓 README：dex1 默认；dex3=assets/scene_hands_cameras.xml（29 body+7/手，nq=50 nu=43）；手指 actuator 见 assets/g1_29dof_with_hand_cameras.xml: 362-408 <motor> ctrlrange 拇指0 ±2.45 其余 ±1.4；default class finger_motor(rng 行 20-22) damping 0.05 armature 0.01 frictionloss 0.1；腕相机 640x480 95° vFOV ZMQ 5555
- VALIDATION.md：验证仅到子集回归（闭合力 20N 帽等），未跑完整 LeRobot/Gym/DDS/ZMQ 链

## [06] xrteleop + il_lerobot 提炼要点（Dex3 遥操/IL 控制）
- teleop/robot_control/robot_hand_unitree.py:27 Dex3_Num_Motors=7；:28-31 DDS topic rt/dex3/{left,right}/{cmd,state}；:141-148 kp=1.5 kd=0.2；:113-135 RIS mode 0x01；:191-196 dex-retargeting 映射；:199-203 14 维 state/action 数组；:213-229 左右手关节序不同（右手 index/middle 互换）；:326-333 dex1 夹爪 kp5/kd0.05 对照
- teleop/robot_control/hand_retargeting.py:50-59 dex3 api 关节名→硬件序映射表
- teleop/teleop_hand_and_arm.py:76 30Hz 录制；:90-95 task json 字段（task-name/goal/desc/steps）
- il_lerobot/eval_robot/robot_control/robot_hand_unitree.py:1-160 与 xrteleop 同源（DDS topic 相同）
- il_lerobot/eval_robot/eval_g1.py:119-125 state=arm_dof+2*ee_dof；:140-147 action 拆分（arm→IK tau；左右手各 ee_dof→共享内存→手控制器）
- il_lerobot/eval_robot/utils/episode_writer.py:17,121-133 data.json 字段 states/actions（30Hz，640x480）

## [07] OpenHomie 提炼要点（自由基座/下蹲）
- 根 README：paper arXiv:2502.13013；2026-07 news 指向 NVlabs/GR00T-WholeBodyControl decoupled_wbc "homie v2 rl policy" 且建议直接用最新 SONIC 模型
- HomieRL/README.md：IsaacGym；三大件 = Upper-body Pose Curriculum / Height Reward Tracking(r_height, r_knee) / Symmetry
- HomieRL/legged_gym/legged_gym/envs/g1/g1_29dof_config.py:118-130 commands 含 height，range [-0.5,0]；:204-251 rewards tracking_base_height=2.0、base_height_target=0.74、clearance_height_target=0.14；:263 action_curriculum=True
- HomieDeploy（C++/LCM，783 文件）为部署侧，未深读（与静态提炼目标无关）

## [08] 避坑核实（一手页面）
- DexUMI 官网 dex-umi.github.io（2026-10-08 抓取）：手硬件为 "XHand and Inspire Hand"，零次提及 Unitree Dex3-1
- GEX arXiv:2506.04982 摘要页（2026-10-08 抓取）：自研 "GX11 tri-finger anthropomorphic hand (11 DoF)"，零次提及 Dex3-1
- 结论：引用这两件时禁写"Dex3-1 上有此结论"（详见 SEARCH-NOTES.md）

## [09] 本组现状对照（数字来源，全部只读）
- 尺寸曲线权威出处: /home/group4/group4_dasc7606c/reports/20261008-125638-qoder-d266d3a9-report.md:12
  "20 mm 0/250、25 mm 4/150（2.7 %）、35 mm 255/392（65.1 %）、50 mm 60/96（62.5 %）"
  同数据也在 reports/20261008-214754-codex-1ac8adb9-report.md:24（921 格结果/319 严格成功；整手碰撞 OFF 5/6、ON 0/6；20mm 8mm 切向半宽可抬升 91-108mm 但 HOLD 前失持）
- 判据/gates: /data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/fixE_tally.csv（success/fail/lift_mm/slip_mm/red gates）
- 关键机制结论: /home/group4/group4_dasc7606c/reports/open-issues.md:501（力与摩擦非瓶颈：N_air 39.62N、mu 1.0→2.5 零改善、tau 2.0N·m >> 需求 0.028N·m；mu=0 同格被楔出；插入标定无解）
  同文件:150（mu 扫描无关）、525（方块容差 0：22 格仅 p21 过门；失败在包围构型）、539（W(-0.425)=37.659mm、间隙 9.95-84.6mm 开口非瓶颈）、628（thumb-index 球心距 p50 34.53mm<35mm；index-middle 恒 57.0mm）、1539（free-base 22/22 全灭、手未碰方块）、1543（ACTION_SCALE 唯四值、yaml 1.0 无效）
- 本组模型: /home/group4/group4_dasc7606c/repos/sonic-bridge/g1/g1_29dof_with_hand.xml:603-609 手指 <motor> ctrlrange 拇指0 ±2.45 其余 ±0.7（HF 官方为 ±1.4，本组低一半）
- 本组抓取脚本: /home/group4/group4_dasc7606c/work/20261006-093203-codex-6385a841/sonic_grasp.py:154,401-412（手指力矩通道）、:466（two-finger contact timeout）、:484-494（gates）；finger_control.py:5-21（PD→torque clip）；source_physics_core.py:111-120（方块 contype/conaffinity 重写、pedestal 半宽 0.0175）
- 本组抓取方块: scene_grasp_hand.xml:49-57（cube 半宽 0.0175=35mm、pedestal 顶 0.741）

## [10] 产出与校验
- /data/group4/20261008-221515-qoder-03c4673f/ws3_static/MIGRATION.md（7 条，含 1 条 N/A 说明）
- /data/group4/20261008-221515-qoder-03c4673f/ws3_static/SEARCH-NOTES.md
- 本文件同步至 logs 流水路径；本地草稿同步至 worker-ws3/
- 校验: 见 [11]

## [11] 最终校验（2026-10-08 23:1x 完成）
- 远端沙盒 /data/group4/20261008-221515-qoder-03c4673f/ws3_static/：
  - MIGRATION.md 112 行 sha256 前缀 26c01372bbf39ce3（定稿不再变）
  - SEARCH-NOTES.md 34 行 sha256 前缀 607079f621a9e46a（定稿不再变）
  - steps-ws3.md（本文件；[11] 补写后重传，sha 以远端现值为准）
- 流水 /home/group4/group4_dasc7606c/logs/20261008-221515-qoder-03c4673f/steps-ws3.md 已同步（9340 B 首版，[11] 补写后重传）
- 本地草稿 E:\qoder\qoder-data\Documents\Qoder\2026-10-08\2aa25fb2\worker-ws3\ 三件同版
- 校验命令: `ssh S4000 'cd <sandbox> && sha256sum *.md'`；结果与上一致（重传前）
- 未做（如实记录）: HomieDeploy C++ 侧未深读；HF 仓 env.py 运行时未拉取；dex-retargeting pypi 可达性未实测
