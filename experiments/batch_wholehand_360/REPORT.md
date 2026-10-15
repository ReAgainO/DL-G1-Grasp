# 批次总结报告（由真实记录生成）

## 一、结论

主实验成功数：A 100/100；B 98/100；C 49/50；D 45/50。物理成功与视频交付分别统计。
A是确定性复现；ARDY仅为姿态先验。MuJoCo3.2.7下的v2基本抓举门，不代表完整Track4或实机。

## 二、操作步骤

数据目录绝对路径：/data/group4/20261009-021611-codex-415484ce
输入：manifest.json；out/<id>/result.json；out/<id>/replay/replay.json 与 grasp.mp4；state/<id>.json。
建议完整保留各 ID 的配置、执行状态、所有阶段返回码及日志；不要只保留成功项。
步骤记录摘要（最多前80行；完整记录另存并链接）：
```text
# 20261009-021611-codex-415484ce 操作流水

## [01] 新批次登记
- 用户请求300主实验、消融及真实视频/双端报告。
- 当前AGENTS完整分段读取；首个大输出截断后补读所有中间和末段，未在截断读取后启动实验。
- 入口README及磁盘公告读取；historical /home0G不等于当前读数。心跳长告示输出截断，仅据已见记录不推断当前活性。
- 300 main native-wholehand MuJoCo3.2.7 trials:100fixed80mm,100randomXY80mm,50randomXY70-90mm,50pairedbackstance20mm; 60 paired ablations no-grip/no-wrist-servo/no-arm-gravity; actual-state video for all runs and representative local download; write own task only, peers/env/assets read-only; no GPU/realrobot/object-stateoverride/weld/externalforces; CPU affinity80-95 max16 distinct cores/max8 concurrent2core jobs; AS4GiB per job/max32GiB working set; per command timeout<=600s, batch wall<=8h; data peak20GiB/home small text<=10MiB; each step logged and server/local MD hash checked
- 自有data1MiB实写探针通过。
[
  {
    "command": [
      "hostname"
    ],
    "output": "worker00039\n",
    "rc": 0
  },
  {
    "command": [
      "date",
      "-Iseconds"
    ],
    "output": "2026-10-09T02:16:11+08:00\n",
    "rc": 0
  },
  {
    "command": [
      "df",
      "-h",
      "/home",
      "/data",
      "/tmp"
    ],
    "output": "Filesystem                         Size  Used Avail Use% Mounted on\n/dev/mapper/ubuntu--vg-home--lv    191G  177G  4.3G  98% /home\n/dev/mapper/data--vg-data--lv       13T  1.5T   11T  13% /data\n/dev/mapper/ubuntu--vg-ubuntu--lv  246G   85G  148G  37% /\n",
    "rc": 0
  },
  {
    "command": [
      "free",
      "-h"
    ],
    "output": "               total        used        free      shared  buff/cache   available\nMem:           1.0Ti        67Gi        26Gi        44Mi       913Gi       931Gi\nSwap:             0B          0B          0B\n",
    "rc": 0
  },
  {
    "read": "/proc/pressure/cpu",
    "output": "some avg10=0.00 avg60=0.00 avg300=0.00 total=4075265457\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
  },
  {
    "read": "/proc/pressure/memory",
    "output": "some avg10=0.00 avg60=0.00 avg300=0.00 total=192450285\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=191349516\n"
  },
  {
    "read": "/proc/pressure/io",
    "output": "some avg10=0.00 avg60=0.00 avg300=0.00 total=301259897\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=299473945\n"
  }
]

- 2026-10-09T02:27:53.837289 Uploaded own batch source from local apply_patch; copied prior own task library and baseline plan read-only. New source preparation; pilots excluded from360.

- 2026-10-09T02:27:53.838619 Pilot configurations frozen: [{"id": "PBASE", "xy_m": [0.35, -0.18], "edge_m": 0.08, "root_x_m": 0, "group": "PILOT", "mass_kg": 0.12, "sampling_seed": null, "no_grip": false, "wrist_servo": true, "gravity_arm_scale": 1}, {"id": "PRAND", "xy_m": [0.369, -0.197], "edge_m": 0.08, "root_x_m": 0, "group": "PILOT", "mass_kg": 0.12, "sampling_seed": null, "no_grip": false, "wrist_servo": true, "gravity_arm_scale": 1}, {"id": "PSIZE", "xy_m": [0.337, -0.163], "edge_m": 0.088, "root_x_m": 0, "group": "PILOT", "mass_kg": 0.12, "sampling_seed": null, "no_grip": false, "wrist_servo": true, "gravity_arm_scale": 1}, {"id": "PBACK", "xy_m": [0.337, -0.163], "edge_m": 0.088, "root_x_m": -0.02, "group": "PILOT", "mass_kg": 0.12, "sampling_seed": null, "no_grip": false, "wrist_servo": true, "gravity_arm_scale": 1}]

- 2026-10-09T02:28:44.399641 Pilot launch {"pid": 2651272, "command": ["taskset", "-c", "80-87", "/usr/bin/python3", "-B", "/data/group4/20261009-021611-codex-415484ce/server_prepare.py", "runpilots"], "cwd": "/data/group4/20261009-021611-codex-415484ce", "started": "2026-10-09T02:28:44.399373", "proc_start_ticks": "83370992"}

- 2026-10-09T02:28:44.436113 Pilot PBASE plan START pid=2651275 command=['timeout', '--kill-after=5', '180', 'taskset', '-c', '80,81', '/data/group4/20261004-205550-qoder-1280b420/env/bin/python', '-B', '/data/group4/20261009-021611-codex-415484ce/batch_plan.py', '--config', '/data/group4/20261009-021611-codex-415484ce/pilots/PBASE.json'] log=/data/group4/20261009-021611-codex-415484ce/logs/PBASE-plan.log

- 2026-10-09T02:28:44.436980 Pilot PRAND plan START pid=2651277 command=['timeout', '--kill-after=5', '180', 'taskset', '-c', '82,83', '/data/group4/20261004-205550-qoder-1280b420/env/bin/python', '-B', '/data/group4/20261009-021611-codex-415484ce/batch_plan.py', '--config', '/data/group4/20261009-021611-codex-415484ce/pilots/PRAND.json'] log=/data/group4/20261009-021611-codex-415484ce/logs/PRAND-plan.log

- 2026-10-09T02:28:44.437106 Pilot PSIZE plan START pid=2651281 command=['timeout', '--kill-after=5', '180', 'taskset', '-c', '84,85', '/data/group4/20261004-205550-qoder-1280b420/env/bin/python', '-B', '/data/group4/20261009-021611-codex-415484ce/batch_plan.py', '--config', '/data/group4/20261009-021611-codex-415484ce/pilots/PSIZE.json'] log=/data/group4/20261009-021611-codex-415484ce/logs/PSIZE-plan.log

- 2026-10-09T02:28:44.437187 Pilot PBACK plan START pid=2651282 command=['timeout', '--kill-after=5', '180', 'taskset', '-c', '86,87', '/data/group4/20261004-205550-qoder-1280b420/env/bin/python', '-B', '/data/group4/20261009-021611-codex-415484ce/batch_plan.py', '--config', '/data/group4/20261009-021611-codex-415484ce/pilots/PBACK.json'] log=/data/group4/20261009-021611-codex-415484ce/logs/PBACK-plan.log

- 2026-10-09T02:28:44.689279 Pilot PRAND plan END {"stage": "plan", "rc": 1, "wall_s": 0.25398683547973633, "command": ["timeout", "--kill-after=5", "180", "taskset", "-c", "82,83", "/data/group4/20261004-205550-qoder-1280b420/env/bin/python", "-B", "/data/group4/20261009-021611-codex-415484ce/batch_plan.py", "--config", "/data/group4/20261009-021611-codex-415484ce/pilots/PRAND.json"], "pid": 2651277, "log": "/data/group4/20261009-021611-codex-415484ce/logs/PRAND-plan.log", "log_sha": "d2f66914395a3e657f963259771829e1c6d7fd1566a27a4503af3c9c5c855f00"}

- 2026-10-09T02:28:44.690256 Pilot PBASE plan END {"stage": "plan", "rc": 1, "wall_s": 0.2543296813964844, "command": ["timeout", "--kill-after=5", "180", "taskset", "-c", "80,81", "/data/group4/20261004-205550-qoder-1280b420/env/bin/python", "-B", "/data/group4/20261009-021611-codex-415484ce/batch_plan.py", "--config", "/data/group4/20261009-021611-codex-415484ce/pilots/PBASE.json"], "pid": 2651275, "log": "/data/group4/20261009-021611-codex-415484ce/logs/PBASE-plan.log", "log_sha": "d2f66914395a3e657f963259771829e1c6d7fd1566a27a4503af3c9c5c855f00"}

- 2026-10-09T02:28:44.690560 Pilot PSIZE plan END {"stage": "plan", "rc": 1, "wall_s": 0.25292062759399414, "command": ["timeout", "--kill-after=5", "180", "taskset", "-c", "84,85", "/data/group4/20261004-205550-qoder-1280b420/env/bin/python", "-B", "/data/group4/20261009-021611-codex-415484ce/batch_plan.py", "--config", "/data/group4/20261009-021611-codex-415484ce/pilots/PSIZE.json"], "pid": 2651281, "log": "/data/group4/20261009-021611-codex-415484ce/logs/PSIZE-plan.log", "log_sha": "d2f66914395a3e657f963259771829e1c6d7fd1566a27a4503af3c9c5c855f00"}

- 2026-10-09T02:28:44.690927 Pilot PBACK plan END {"stage": "plan", "rc": 1, "wall_s": 0.2532830238342285, "command": ["timeout", "--kill-after=5", "180", "taskset", "-c", "86,87", "/data/group4/20261004-205550-qoder-1280b420/env/bin/python", "-B", "/data/group4/20261009-021611-codex-415484ce/batch_plan.py", "--config", "/data/group4/20261009-021611-codex-415484ce/pilots/PBACK.json"], "pid": 2651282, "log": "/data/group4/20261009-021611-codex-415484ce/logs/PBACK-plan.log", "log_sha": "d2f66914395a3e657f963259771829e1c6d7fd1566a27a4503af3c9c5c855f00"}

- 2026-10-09T02:30:43.956318 Uploaded own batch source from local apply_patch; copied prior own task library and baseline plan read-only. New source preparation; pilots excluded from360.
```
完整步骤记录：/home/group4/group4_dasc7606c/logs/20261009-021611-codex-415484ce/steps.md

明确提供的已执行命令：
timeout 180 /usr/bin/python3 -B /data/group4/20261009-021611-codex-415484ce/server_prepare.py freeze
timeout 60 /usr/bin/python3 -B /data/group4/20261009-021611-codex-415484ce/server_prepare.py launch
timeout --kill-after=5 580 taskset -c 80,81 /data/group4/20261004-205550-qoder-1280b420/env/bin/python -B /data/group4/20261009-021611-codex-415484ce/audit_batch.py --output audit-final.json
timeout --kill-after=5 580 taskset -c 80,81 /data/group4/20261004-205550-qoder-1280b420/env/bin/python -B /data/group4/20261009-021611-codex-415484ce/verify_videos.py

计划资源边界：bounded、noGPU；须以任务日志/资源记录核实。服务器与本地 Markdown 双端 SHA 核对须附两端路径及摘要，不得由本脚本虚构。

## 三、实测证据

manifest SHA-256：1757e01b98747133052fe06f97f44c485e043277fb276e0c9df2ab8b6621b3b3
实验定义与资源协议见同目录PROTOCOL.md：A固定(.35,-.18)m/80mm；B x[.33,.37]、y[-.20,-.16]m/80mm；C同位置池、均匀70–90mm；D精确配对C且机器人初始后撤2cm，物体/桌世界坐标不变；均120g。
控制链为ARDY near_s42第99帧姿态先验→几何/参考轨迹规划→SONIC v1.1身体控制＋腕参考辅助修正→独立右手7关节PD；不是完整ARDY时变生成动作驱动。C/D终端按同一世界物体重新规划。
左右整手各7原生碰撞几何及掌/腕碰撞启用，原合成球垫碰撞关闭。自由基座/自由物体、无weld/mocap/物体执行器；仅控制执行器。手指armature=.1、PD40/2；右臂身体PD增益为基准×3、阻尼×sqrt(3)*2，并有重力前馈。模型/增益已调参，不代表实机参数验证。
所有试验 ID 与结果字段见同目录 summary.json；视频逐项核验状态见 video-index.md。
主300与消融60独立汇总：{"main_300": {"groups": ["A", "B", "C", "D"], "planned_denominator": 300, "counts": {"success": 292, "planning_refused": 0, "physics_failure": 8, "infrastructure_error": 0, "not_started": 0}, "success": 292, "actual_grasp_execution_count": 300, "valid_video_count": 300, "missing_video_count": 0, "success_per_planned": 0.9733333333333334, "success_per_grasp_execution": 0.9733333333333334}, "ablation_60": {"groups": ["NGR", "NWS", "NGF"], "planned_denominator": 60, "counts": {"success": 25, "planning_refused": 0, "physics_failure": 35, "infrastructure_error": 0, "not_started": 0}, "success": 25, "actual_grasp_execution_count": 60, "valid_video_count": 60, "missing_video_count": 0, "success_per_planned": 0.4166666666666667, "success_per_grasp_execution": 0.4166666666666667}}
MuJoCo3.2.7；环境、模型/库/权重SHA和dt见summary.json/runtime_stamp。无戳contact_frames及planning_refusal原始诊断不进入数值引用链；门结果以已盖章result.json和trajectory.npz为准。
| 组 | 计划分母 | 终态计数 | success/planned | success/实际抓取 | 有效视频 | 视频缺失/无效 |
|---|---:|---|---:|---:|---:|---:|
| A | 100 | {"success": 100, "planning_refused": 0, "physics_failure": 0, "infrastructure_error": 0, "not_started": 0} | 1.0000 | 1.0000 | 100 | 0 |
| B | 100 | {"success": 98, "planning_refused": 0, "physics_failure": 2, "infrastructure_error": 0, "not_started": 0} | 0.9800 | 0.9800 | 100 | 0 |
| C | 50 | {"success": 49, "planning_refused": 0, "physics_failure": 1, "infrastructure_error": 0, "not_started": 0} | 0.9800 | 0.9800 | 50 | 0 |
| D | 50 | {"success": 45, "planning_refused": 0, "physics_failure": 5, "infrastructure_error": 0, "not_started": 0} | 0.9000 | 0.9000 | 50 | 0 |
| NGR | 20 | {"success": 0, "planning_refused": 0, "physics_failure": 20, "infrastructure_error": 0, "not_started": 0} | 0.0000 | 0.0000 | 20 | 0 |
| NWS | 20 | {"success": 5, "planning_refused": 0, "physics_failure": 15, "infrastructure_error": 0, "not_started": 0} | 0.2500 | 0.2500 | 20 | 0 |
| NGF | 20 | {"success": 20, "planning_refused": 0, "physics_failure": 0, "infrastructure_error": 0, "not_started": 0} | 1.0000 | 1.0000 | 20 | 0 |
成功样例与真实 physics_failure 样例仅从各自组内选最低数值 ID；未找到的类别明确为无样例：
| 组 | 类别 | ID | 抓取执行视频有效 | 服务器视频路径 |
|---|---|---|---|---|
| A | success | A000 | True | /data/group4/20261009-021611-codex-415484ce/out/A000/replay/grasp.mp4 |
| A | physics_failure | 无样例 | 不适用 | 无；不借用其他组或消融替代 |
| B | success | B000 | True | /data/group4/20261009-021611-codex-415484ce/out/B000/replay/grasp.mp4 |
| B | physics_failure | B051 | True | /data/group4/20261009-021611-codex-415484ce/out/B051/replay/grasp.mp4 |
| C | success | C000 | True | /data/group4/20261009-021611-codex-415484ce/out/C000/replay/grasp.mp4 |
| C | physics_failure | C046 | True | /data/group4/20261009-021611-codex-415484ce/out/C046/replay/grasp.mp4 |
| D | success | D000 | True | /data/group4/20261009-021611-codex-415484ce/out/D000/replay/grasp.mp4 |
| D | physics_failure | D011 | True | /data/group4/20261009-021611-codex-415484ce/out/D011/replay/grasp.mp4 |
| NGR | success | 无样例 | 不适用 | 无；不借用其他组或消融替代 |
| NGR | physics_failure | NGR000 | True | /data/group4/20261009-021611-codex-415484ce/out/NGR000/replay/grasp.mp4 |
| NWS | success | NWS000 | True | /data/group4/20261009-021611-codex-415484ce/out/NWS000/replay/grasp.mp4 |
| NWS | physics_failure | NWS002 | True | /data/group4/20261009-021611-codex-415484ce/out/NWS002/replay/grasp.mp4 |
| NGF | success | NGF000 | True | /data/group4/20261009-021611-codex-415484ce/out/NGF000/replay/grasp.mp4 |
| NGF | physics_failure | 无样例 | 不适用 | 无；不借用其他组或消融替代 |

planning_refused 样例 ID：
A: 无
B: 无
C: 无
D: 无
NGR: 无
NWS: 无
NGF: 无


## 四、失败项与原因

以下列阶段rc、错误/日志路径及physics reason；基础设施错误附日志尾部，常规physics_failure仅附各组最低ID样例原文；全部阶段记录见summary.json。
超时/基础设施子类计数：{}
首次独立审计保留在audit_batch.json/final-audit.log：checked=260，断言失败数=100。A沿用旧自有任务meshdir，硬编码新路径XML哈希误报；只读诊断见audit-first-diagnostic.json与robot-identity-diagnostic.json。修正后的audit-final.json逐项检查A旧XML固定SHA、仅meshdir路径替换后精确匹配新XML、且两路径解析到同一只读网格资产。没有重写物理源码、XML、轨迹或成功门；原始失败及audit-v1-source.py均保留。

ID B051 [B] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["腕局部滑移：0.017550990820702526m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/B051-plan.log
```text
{"id": "B051", "geometry_pass": true, "best": {"axis": 0, "seed": "frozen_baseline_warmstart", "targets": [[0.2615456050949919, -0.18826524746236642, 0.765], [0.40154560509499193, -0.15976524746236642, 0.765], [0.40154560509499193, -0.21676524746236642, 0.765]], "q": [-0.1626135079240234, -0.5897809612655831, 0.5123052809132834, 0.07034461911503014, -0.8454609540553291, 0.4169666414488542, 0.015939511297230972, 0.11625291558656478, 0.7213098154272974, -1.4536571458481775, 0.37590388166720023, 0.7701695669397414, 0.32762720300306003, 0.8445897501601128], "pad_error_m": 1.3683919661786913e-05, "min_bone_cube_gap_m": 0.00764033178551804, "min_bone_table_gap_m": 0.02558776918304906, "nfev": 100, "rough_nfev": 20}}

```
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/B051-physics.log
```text
e38d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": 0.0}, "synthetic_pads": "DISABLED: inherited spheres visual markers only; seven original right collision geoms and palm/wrist remain physical"}

```
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/B051-render.log
```text
"vendor_converter_sha": "3d3d16b80c24e6a68f329504edd72b400f2df998ca7bdfddbf548674a9e79fa5", "converter_asset_sha": "5d76cf92f00dd49d6eb9fae38d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": 0.0}}

```

ID B071 [B] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["腕局部滑移：0.012906965381993105m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/B071-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/B071-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/B071-render.log

ID C046 [C] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：2407/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/C046-plan.log
```text
{"id": "C046", "geometry_pass": true, "best": {"axis": 0, "seed": "frozen_baseline_warmstart", "targets": [[0.28782324088484373, -0.17465580554409624, 0.7685719710869345], [0.4349671830587128, -0.14615580554409624, 0.7685719710869345], [0.4349671830587128, -0.20315580554409624, 0.7685719710869345]], "q": [-0.31499854818404033, -0.5251886823499586, 0.5610143794519082, 0.21382558237392596, -0.8289522009820716, 0.4344198219609195, 0.05322147532721061, 0.18897641918207264, 0.7213112179729797, -1.4889737245592314, 0.2869042886803848, 0.7521864175991189, 0.24169599569862402, 0.8153060476154197], "pad_error_m": 1.359161109038619e-05, "min_bone_cube_gap_m": 0.0009997747721834926, "min_bone_table_gap_m": 0.0294086049226413, "nfev": 46, "rough_nfev": 41}}

```
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/C046-physics.log
```text
e38d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": 0.0}, "synthetic_pads": "DISABLED: inherited spheres visual markers only; seven original right collision geoms and palm/wrist remain physical"}

```
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/C046-render.log
```text
"vendor_converter_sha": "3d3d16b80c24e6a68f329504edd72b400f2df998ca7bdfddbf548674a9e79fa5", "converter_asset_sha": "5d76cf92f00dd49d6eb9fae38d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": 0.0}}

```

ID D011 [D] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：2466/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.034623745967063524m，门≤.01m", "关节超限：0.021486904338259144rad，门<.002rad"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D011-plan.log
```text
{"id": "D011", "geometry_pass": true, "best": {"axis": 0, "seed": "frozen_baseline_warmstart", "targets": [[0.29307244817712375, -0.18063117555460434, 0.7697657322814441], [0.442603912740012, -0.15213117555460434, 0.7697657322814441], [0.442603912740012, -0.20913117555460434, 0.7697657322814441]], "q": [-0.4567431857313896, -0.48074973010696215, 0.5316362947530051, 0.446403034003089, -0.8346079477335394, 0.3208799551997919, 0.049037341555657955, 0.06211311688095658, 0.7157256150632304, -1.4164500976010608, 0.2791662016850304, 0.7714587907505768, 0.2700996704383458, 0.7841739848282976], "pad_error_m": 1.215793501626101e-06, "min_bone_cube_gap_m": 0.0009967784335884744, "min_bone_table_gap_m": 0.03061032070578351, "nfev": 22, "rough_nfev": 80}}

```
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D011-physics.log
```text
8d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": -0.02}, "synthetic_pads": "DISABLED: inherited spheres visual markers only; seven original right collision geoms and palm/wrist remain physical"}

```
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D011-render.log
```text
endor_converter_sha": "3d3d16b80c24e6a68f329504edd72b400f2df998ca7bdfddbf548674a9e79fa5", "converter_asset_sha": "5d76cf92f00dd49d6eb9fae38d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": -0.02}}

```

ID D017 [D] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["腕局部滑移：0.021734245190701836m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D017-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D017-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D017-render.log

ID D025 [D] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.12209796387644045m，门≤.01m", "关节超限：0.009647875889045032rad，门<.002rad"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D025-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D025-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D025-render.log

ID D027 [D] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：2450/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.010111097901909854m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D027-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D027-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D027-render.log

ID D046 [D] physics_failure: object_fell
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["未完整运行：object_fell", "保持步数不足：0<2000", "关节超限：0.0028667880897533804rad，门<.002rad"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D046-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D046-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/D046-render.log

ID NGR000 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.11411655028095306m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR000-plan.log
```text
{"id": "NGR000", "geometry_pass": true, "best": {"axis": 0, "seed": "frozen_baseline_warmstart", "targets": [[0.2789161074873625, -0.18343058982588248, 0.765], [0.4189161074873625, -0.15493058982588248, 0.765], [0.4189161074873625, -0.21193058982588248, 0.765]], "q": [-0.200100546477358, -0.559165242688773, 0.5352781070531053, 0.15083526404625572, -0.8407249625844274, 0.39896407132123524, -0.02874077805060887, -0.009927060348257032, 0.7213107852630454, -1.6908641823077215, 0.2738424293857311, 0.7326236945555566, 0.22555208526681816, 0.8096493729386623], "pad_error_m": 1.2024845435542033e-05, "min_bone_cube_gap_m": 0.0010050996143443625, "min_bone_table_gap_m": 0.02606499847082988, "nfev": 100, "rough_nfev": 46}}

```
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR000-physics.log
```text
e38d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": 0.0}, "synthetic_pads": "DISABLED: inherited spheres visual markers only; seven original right collision geoms and palm/wrist remain physical"}

```
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR000-render.log
```text
"vendor_converter_sha": "3d3d16b80c24e6a68f329504edd72b400f2df998ca7bdfddbf548674a9e79fa5", "converter_asset_sha": "5d76cf92f00dd49d6eb9fae38d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": 0.0}}

```

ID NGR001 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.11085459816052955m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR001-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR001-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR001-render.log

ID NGR002 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.1155333683083993m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR002-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR002-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR002-render.log

ID NGR003 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.11675943395931568m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR003-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR003-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR003-render.log

ID NGR004 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10306919071686058m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR004-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR004-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR004-render.log

ID NGR005 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10604941750026846m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR005-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR005-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR005-render.log

ID NGR006 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10738270782501358m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR006-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR006-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR006-render.log

ID NGR007 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10376387046552712m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR007-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR007-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR007-render.log

ID NGR008 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.1150300318369848m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR008-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR008-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR008-render.log

ID NGR009 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.11393008273700479m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR009-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR009-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR009-render.log

ID NGR010 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10648110917253877m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR010-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR010-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR010-render.log

ID NGR011 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.11664824380567872m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR011-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR011-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR011-render.log

ID NGR012 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.1167830470897852m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR012-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR012-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR012-render.log

ID NGR013 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10645550996667001m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR013-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR013-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR013-render.log

ID NGR014 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.11313299084019152m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR014-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR014-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR014-render.log

ID NGR015 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.11610525834650937m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR015-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR015-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR015-render.log

ID NGR016 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10852036451117476m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR016-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR016-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR016-render.log

ID NGR017 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10528214232571013m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR017-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR017-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR017-render.log

ID NGR018 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10978730564660276m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR018-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR018-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR018-render.log

ID NGR019 [NGR] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10909511586676825m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR019-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR019-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NGR019-render.log

ID NWS002 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.09079206580903594m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS002-plan.log
```text
{"id": "NWS002", "geometry_pass": true, "best": {"axis": 0, "seed": "frozen_baseline_warmstart", "targets": [[0.2980873058289211, -0.18374258435686217, 0.765], [0.43808730582892114, -0.15524258435686217, 0.765], [0.43808730582892114, -0.21224258435686216, 0.765]], "q": [-0.3007356436492382, -0.5326209331739016, 0.5492242445616444, 0.28279750689778815, -0.8116295867952472, 0.3669939526167403, -0.04738555506856292, 0.04163331794974416, 0.7212765572802674, -1.6720282894975178, 0.3016778094248236, 0.7057486019960268, 0.25718190803874863, 0.7723770421499615], "pad_error_m": 1.095769320061836e-05, "min_bone_cube_gap_m": 0.0009976879226344382, "min_bone_table_gap_m": 0.02611109080667362, "nfev": 77, "rough_nfev": 80}}

```
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS002-physics.log
```text
e38d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": 0.0}, "synthetic_pads": "DISABLED: inherited spheres visual markers only; seven original right collision geoms and palm/wrist remain physical"}

```
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS002-render.log
```text
"vendor_converter_sha": "3d3d16b80c24e6a68f329504edd72b400f2df998ca7bdfddbf548674a9e79fa5", "converter_asset_sha": "5d76cf92f00dd49d6eb9fae38d7d38e46886848b602ac691051e886c3bcccfb1", "joint_names": ["left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint", "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint", "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint", "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint", "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint", "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint", "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint"], "body_order": "MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly", "text": "A person reaches forward with their right hand to grab a small object on a table.", "conversion": "native local_rot_mats + root_positions; no angles inferred from posed_joints"}, "root_x_initial_m": 0.0}}

```

ID NWS003 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.09259399777974192m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS003-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS003-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS003-render.log

ID NWS005 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.09370037852192888m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS005-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS005-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS005-render.log

ID NWS006 [NWS] physics_failure: object_fell
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["未完整运行：object_fell", "保持步数不足：1093<2000", "保持阶段有不安全步：623/1093安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.27415385241427626m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS006-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS006-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS006-render.log

ID NWS008 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["腕局部滑移：0.010127777232897792m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS008-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS008-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS008-render.log

ID NWS009 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：1300/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10178926677689348m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS009-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS009-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS009-render.log

ID NWS010 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.09108395475906873m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS010-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS010-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS010-render.log

ID NWS011 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["腕局部滑移：0.010162356649260629m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS011-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS011-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS011-render.log

ID NWS012 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["腕局部滑移：0.016645316280219903m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS012-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS012-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS012-render.log

ID NWS013 [NWS] physics_failure: object_fell
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["未完整运行：object_fell", "保持步数不足：0<2000", "腕局部滑移：0.28033336996046554m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS013-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS013-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS013-render.log

ID NWS014 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：0/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10001522983786999m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS014-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS014-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS014-render.log

ID NWS015 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：450/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.10414948293872832m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS015-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS015-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS015-render.log

ID NWS016 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["保持阶段有不安全步：1985/2500安全；此项含高度/桌接触/对向接触/双足/非足接触，汇总值不能定位每个1ms的首次失败", "腕局部滑移：0.0996519922451192m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS016-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS016-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS016-render.log

ID NWS018 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["腕局部滑移：0.02020401048853694m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS018-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS018-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS018-render.log

ID NWS019 [NWS] physics_failure: complete
未过的运行时门（据原始已盖章汇总，不推断未记录的首次接触时刻）：["腕局部滑移：0.01911166106190607m，门≤.01m"]
  stage=0 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS019-plan.log
  stage=1 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS019-physics.log
  stage=2 rc=0 log=/data/group4/20261009-021611-codex-415484ce/logs/NWS019-render.log

未完成项目按 not_started 统计；规划拒绝不是物理失败，safe-standing 回放不是抓取执行证据。视频索引有效不等于物理成功。

## 五、下一步建议

逐ID核验planning refusal是否由规划门产生、path阶段是否真的运行、hold/servo退出原因与rc；将gate误差和物理reason关联至同ID配置及轨迹。
成功项复核执行门、hold_pass_steps/hold_safe_steps及关键gate误差；失败项检查首次接触顺序、超时阶段和是否进入真实grasp路径。视频交付单独核对源result与trajectory哈希。
C/D与消融/B按source_baseline_trial配对。pipeline四格比较success与非success，error/not_started另格；valid-physics四格仅含success/physics_failure：
D_vs_C: pipeline四格={"both_success": 45, "baseline_only_success": 4, "neither_success": 1}; 被排除配对的infra/not_started分别计数={"infrastructure_error": 0, "not_started": 0}（两种状态可同时出现，勿相加作分母）；valid-physics四格={"both_success": 45, "baseline_only_success": 4, "neither_success": 1}; 完整物理配对=50; success差值(target-baseline)=-0.08
NGR_vs_B: pipeline四格={"baseline_only_success": 20}; 被排除配对的infra/not_started分别计数={"infrastructure_error": 0, "not_started": 0}（两种状态可同时出现，勿相加作分母）；valid-physics四格={"baseline_only_success": 20}; 完整物理配对=20; success差值(target-baseline)=-1.0
NWS_vs_B: pipeline四格={"both_success": 5, "baseline_only_success": 15}; 被排除配对的infra/not_started分别计数={"infrastructure_error": 0, "not_started": 0}（两种状态可同时出现，勿相加作分母）；valid-physics四格={"both_success": 5, "baseline_only_success": 15}; 完整物理配对=20; success差值(target-baseline)=-0.75
NGF_vs_B: pipeline四格={"both_success": 20}; 被排除配对的infra/not_started分别计数={"infrastructure_error": 0, "not_started": 0}（两种状态可同时出现，勿相加作分母）；valid-physics四格={"both_success": 20}; 完整物理配对=20; success差值(target-baseline)=0.0
物理arrays及消融beforeclose独立审计：/data/group4/20261009-021611-codex-415484ce/audit-final.json
审计边界：NPZ为每20ms抽样状态；成功门核对使用仿真器每1ms评估后记录的汇总值。核对值与success的一致性，不宣称独立重算全部1ms接触/成功门。视频另经全片解码及逐片身份/源哈希核验。
独立核验格数=360，致命证据错误=0，对拍限制警告=38
警告：部分独立重规划输入在控制开关生效前不逐字节相同。最大绝对差及各pair详见audit-final.json；对应消融只能作为同场景描述对照，不能标为严格同输入因果消融。没有事后放宽v2成功门，也没有删除这些样本。
实际非同输入配对按组计数：{"NGR": 8, "NWS": 8, "NGF": 6}；包含NWS时，其独立规划产生的生效前差异亦保留，不以差异小为由改标严格因果。
另逐对核验完整预计算body/hand/wrist参考是否逐字节相同。NGF从t=0生效，没有开关前时间段，不能以空前缀或初始状态相同冒充严格前处理证明；最终只作本版本同场景对照解释。
后续优先级（建议，尚未实施，不改变本批结果）：
1. 新批次将B对照的完整规划/参考固定复制给消融，逐数组核验开关生效前状态与输入，解决非严格同输入问题。
2. 将接近阶段的真实物体接触纳入门，先消除提前碰撞，再改为接触反馈触发闭手/试抬；现有参考几何无穿透不等于动力学无碰撞。
3. 将保持阶段从当前约2.5秒延长至10秒，保留现有高度、对向接触、双足、局部滑移和关节门，记录长时间掉落。
4. 分批拓宽当前±2cm位置、70–90mm边长和120g固定质量的场景；目前不能外推到任意桌面位置/质量。
5. 独立接入完整ARDY时变动作，对照常量/无ARDY先验；并在第二MuJoCo版本同样本复验，之后再谈ARDY贡献与跨版本稳健性。
如需复用姿态先验，应另验证完整动作闭环；本批次 success gate 是 v2 wrist-local-support，不代表 v5/v6。

## 六、复现方法

仅列操作者传入并标记为已执行的命令：
timeout 180 /usr/bin/python3 -B /data/group4/20261009-021611-codex-415484ce/server_prepare.py freeze
timeout 60 /usr/bin/python3 -B /data/group4/20261009-021611-codex-415484ce/server_prepare.py launch
timeout --kill-after=5 580 taskset -c 80,81 /data/group4/20261004-205550-qoder-1280b420/env/bin/python -B /data/group4/20261009-021611-codex-415484ce/audit_batch.py --output audit-final.json
timeout --kill-after=5 580 taskset -c 80,81 /data/group4/20261004-205550-qoder-1280b420/env/bin/python -B /data/group4/20261009-021611-codex-415484ce/verify_videos.py
从全新目录复现前，先按完整路径复制源代码、配置和依赖清单并核验SHA；随后运行已记录的实际命令。计划或帮助命令不得表述为已执行。
逐项复核 summary.json、video-index.md、state 阶段日志；对本地/服务器 Markdown 分别计算 SHA-256 并记录完整路径。
重要：本脚本只汇总现存记录，不启动仿真，不补跑，也不把计划命令写成实测。
