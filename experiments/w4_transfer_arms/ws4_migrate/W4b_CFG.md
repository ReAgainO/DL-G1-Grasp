# W4b_CFG.md — 臂1：真机闭爪构型注入对照实验（W4b）

- 任务: 20261008-221515-qoder-03c4673f / worker-ws4b（子代理，产出归父会话 TASKID，不新建 claim）
- 机器: worker00039；副本 `ws4_migrate/rep_ext_cfg`（自 rep_base 复制 + 5 处改动；**rep_base 未再改动**，只读参照）
- 结论: **注入无效且有害**。12 格处理臂 0 成功；2 个基线成功格（b25_12_04、b25_04_01）双双退化为 CLOSE 超时；
  近成功格（b25_02_06）退化为超时；8 个"抬不起+滑移"失败格无一改善（4× 退化为 CLOSE 超时、4× 退化为更早的 ALIGN 超时）；
  唯一"跑完全程"的 b25_00_10 方块被打下桌（slip 114mm）。
  **改善 0 格、持平 0 格、恶化 12 格。未改动任何成功门/阈值/`.flags_flat`。**

---

## 1. 注入物与映射（按关节名对齐，不是拷数字）

- 先验（W2, `/data/group4/20261008-221515-qoder-03c4673f/ws2_dataset/FINDING.md §5`，
  sha256=0022d2c1…，cfg_hold_final 中位 n=81）数据集是**左手**，槽位序 [middle_0,middle_1,index_0,index_1,thumb_0,thumb_1,thumb_2]。
- 本组仿真用**右手**（actuator 36..42 = XML:603-609 顺序 thumb_0,thumb_1,thumb_2,index_0,index_1,middle_0,middle_1）。
- 右手指限位（rep XML:467-537 实测）是左手限位的**符号镜像**：thumb_0 [-1.0472,1.0472]、thumb_1 [-1.0472,0.7243]、
  thumb_2 [-2.0944,0]、index_0/middle_0 [-0.192,1.8326]、index_1/middle_1 [0,2.0944]。
  ⇒ 不镜像时 middle_1=-1.488、index_1=-1.481 直接落在 [0,2.0944] 之外 ⇒ **必须 q_right=-q_left**。
- 注入向量（`grip_real_map.json`，sonic-bridge 右手段）:
  **[-0.0151, -0.6207, -0.6749, 0.9594, 1.4810, 0.9738, 1.4879]**
  （idx/mid 的 W2"待核"交换影响 ≤0.015 rad，不material）
- 旁证: 内置 CLOSED recipe 拇指段 (0,-.60,-.88) 与真机镜像后 (-0.015,-0.621,-0.675) 几乎相同（thumb_1 差 0.02 rad）。

## 2. FK 位姿差（判据：差太大先修正再跑；`logs/fk_cfg.out`）

同一 CLOSE 入场腕位姿（b25_12_04），A=原 close_hand [0,-.60,-.88,1.40,.08,1.40,.08]、B=注入构型、C=基线实际 IK 输出:

| 量 | A | B | C |
|---|---|---|---|
| 拇指↔中指 pad 间距 | 48.5 mm | **43.9 mm**（>5mm 安全检查通过） | 43.4 mm |
| 拇指 pad 到方块心 | 26.4 mm | 19.6 mm | 21.6 mm |
| 中指 pad 到方块心 | 23.1 mm | 36.8 mm | 22.9 mm |
| contact_frame 点误差 | 5.0 mm | **16.4 mm** | 5.0 mm |
| A→B pad 位移 | — | 拇指 9.2 / 食指 **35.0** / 中指 **36.3** mm（指尖上扫 +29~30mm z、+10mm x） | A→C ≤5mm |

判定: **映射正确**（值域合规、拇指与内置 recipe 独立吻合、pad 反对置结构仍在），但**姿态差显著**——
差异集中在 index/middle 远端关节（0.08→1.48 rad = 80°），真机构型近"握拳式"（power grasp），
本管线要求的是三 pad 等高的"平面捏"（flat pinch）。且 contact_frame（臂的目标点定义）平移 14.4mm。

## 3. 冒烟三连（全部通过）

| 冒烟 | 做法 | 结果 |
|---|---|---|
| (a) 旁路无损 | 不传参跑 b25_12_04 vs W4a 基线 | 12/12 物理数组 **bitwise_equal=True**（max_diff=0.000e+00）、结果字段/gates/adaptive_calls(111) 全 SAME；stdout 无 GRIP_TARGET_JSON |
| (b) 通道无副作用 | 传"默认原值"json 再跑 | vs (a) **12/12 逐位同**；stdout `applied:false`；result `identity_noop=True`；IK 仍 111 次 |
| (c) 目标真的生效 | 传真机映射 json 跑 b25_00_10 | stdout GRIP_TARGET_JSON `applied:true`；result `adaptive_ik_bypassed=True, adaptive_hand_calls=0`；meta 记 `--grip-target-json=`；trajectory `min|hand_reference−目标|=0.0000`（12 格中 8 格命中 0.0 精确命中，其余 4 格因未进 CLOSE 而停在 OPEN） |

（判据实现: 注入值与内置 recipe 逐位相等即视为恒等 no-op ⇒ 恒等点可证；不等时**旁路 0.1s AdaptiveHand 重解**，
静态目标即下发目标——"目标不被 IK 重写"。）

## 4. 对照表（CUT=0 于 rep_ext_cfg 新副本；基线=S1000 b25 全层 W4a 聚合 + rep_base 5 格 W4a 复跑）

| 格 | 类别/基线 fb | 基线 succ/lift/slip(mm) | 注入后 | 注入 lift/slip(mm) | 注入 IK calls | 判定 |
|---|---|---|---|---|---|---|
| b25_12_04 | S / 0 | True 121.3 / 4.24 | **two-finger contact timeout** | — | 0 | 恶化（成功→失败） |
| b25_04_01 | S / 30 | True 123.8 / 3.78 | **two-finger contact timeout** | — | 0 | 恶化 |
| b25_02_06 | 近成功(仅桌子门) / 0 | False 121.5 / 3.69 | **two-finger contact timeout** | — | 0 | 恶化 |
| b25_00_10 | CLOSE 超时 / 0 | False timeout | 跑完全程，但方块被打下桌 | **-757.0 / 114.41** | 0 | 恶化（物理更差） |
| b25_10_18 | lift+slip / 0 | False -0.1 / 15.73 | alignment timeout | — | 0 | 恶化 |
| b25_02_09 | lift+slip / 0 | False -0.1 / 15.88 | two-finger contact timeout | — | 0 | 恶化 |
| b25_12_05 | lift+slip / 0 | False -0.1 / 18.05 | two-finger contact timeout | — | 0 | 恶化 |
| b25_10_19 | lift+slip / 0 | False -0.1 / 20.26 | alignment timeout | — | 0 | 恶化 |
| b25_00_18 | lift+slip / 0 | False -0.1 / 21.92 | two-finger contact timeout | — | 0 | 恶化 |
| b25_12_10 | lift+slip / 0 | False -0.1 / 26.49 | alignment timeout | — | 0 | 恶化 |
| b25_04_04 | lift+slip / 0 | False -0.1 / 46.77 | two-finger contact timeout | — | 0 | 恶化 |
| b25_12_14 | lift+slip / 0 | False -6.1 / 151.29 | alignment timeout | — | 0 | 恶化 |

汇总: 注入臂 **success 0/12**；fail: ran-all 1、two-finger contact timeout 7、alignment timeout 4（`fixE_tally.py` 输出见 `logs/grip_arm_tally.out`）。
基线成功格丢失 2、新增成功 0。

选格规则（照 W4a §3.3）: 优先 fallback=0（reference_filter.certified_continuation_steps=0，W4a 证该类逐位可比）；
本臂 11/12 格 fb=0（唯一例外 b25_04_01 fb=30，仅类别级对照）。阳性对照 2 成功 + 1 近成功；失败 8 格覆盖 lift≈0/slip 15→151mm 全谱；1 格 CLOSE 超时。

## 5. 失败机制（有数字）

1. **构型-任务错配（主因）**: 真机先验是"深卷握持"（index/middle 远端 1.48 rad），本管线按"三 pad 平面捏"工作：
   臂的目标点 `contact_frame`（=对置 pad 沿 pad 轴内推 support radius 的"预期方块心"）随注入构型**平移 14.4mm**，
   且 index/middle 指垫在注入构型下悬于方块顶面之上 ~17-20mm。结果: 手指闭合时凑不出两指同时接触。
2. **CLOSE 超时（7 格）定义 = 5s 内从未达到"≥2 pad 力>0.1N 且持续 0.2s"**（sonic_grasp.py:513-516，未改门）。
   实测 b25_12_04: CLOSE 5.5s 窗口 F_thumb max=0.00N、F_middle max=0.00N、**只有食指 F_index=0.59N 蹭到**，
   方块被蹭走 (dx,dy)=(-11.3,-14.7)mm ⇒ 非对置接触、无夹持。
3. **ALIGN 超时（4 格）**: ALIGN 需 poserr<7mm（或近接触）+ flat 高度差<12mm 且持续 0.2s，8s 上限（:506-512）。
   注入构型把"预期方块心"目标和平垫约束同时扰动 ⇒ 4 格 8s 内没收敛（对照组 b25_12_04 的 ALIGN 从 1.7s 拉长到 6.1s）。
4. **唯一"跑完全程"格 b25_00_10**: 拇指 5.97N + 中指 4.36N 确实夹上了（基线该格反而连接触都没有），
   但夹持轴向错位，抬升/保持段方块被搓出：dx=+64.7mm、dy=-23.3mm、随后落桌到地板（lift_min=-757mm、slip=114mm）——
   "夹上了但拿不住"，比基线（原地超时）物理上更差。
5. 全链路扰动幅（预期内）: b25_12_04 注入 vs 基线首个 qpos 分叉在 frame 441 (t=17.64s, APPROACH，即 `close_hand` 进入
   clearance/branch 几何之后)，重叠段 max|Δqpos|=1.64 rad；hand_reference 首个分叉在 CLOSE 入口 (t=46.96s)。
   ⇒ 这是"构型进入全链路"的效应（W4a §1b 注意项已如实记录），不是纯"末端目标"效应。

## 6. 结论与后续建议

- **注入真机 hold 段闭爪构型不能改善本组 25mm 抓取**（12 格 0 成功、2 个既有成功直接丢失）。当前管线的成功机理是
  thumb↔middle 对置 pad 的 1.5mm 预压平面捏 + 0.1s 自适应 IK 目标跟踪；用外部"握拳式"静态构型替换它，
  等于同时改掉了臂的目标点定义、接触法向与垫高约束，收益为负。
- 有价值的副产品: (i) 注入通道恒等点逐位可证（(a)/(b) 冒烟），以后任何"目标注入"实验都可复用该旁路骨架;
  (ii) 真机数据与 sim 的**符号镜像**已用限位硬约束证死，不需再猜; (iii) "夹上了但拿不住"的 b25_00_10 一例说明
  本任务对**接触轴向**敏感（力不是问题、方向才是）。
- 建议（不在本任务执行）: 若还要用该先验，应走 W4a 方案 B（只作 seed 保留自适应跟踪）或仅注入**拇指段**（与 recipe 吻合的那 3 维），
  而不是整手静态替换；20mm 层（c20d/c20f, 0/250）本先验样本更弱，本实验不支持优先投在那里。
- 未渲染 mp4: 本臂 0 成功（任务条件"若出现 success"未触发）。

## 7. 产物

- 代码/配置: `ws4_migrate/rep_ext_cfg/rep/sonic_grasp.py`(sha256 f668518a…)、`run_fixE.sh`(61d5ab3f…)、`grip_arm_batch.sh`、`grip_arm_jobs.txt`
- 先验与脚本: `ws4_migrate/grip_real_map.json`、`grip_default.json`、`fk_cfg.py`、`b25_select.py`、`traj_cmp.py`、`arm_report.py`
- 日志: `ws4_migrate/logs/{fk_cfg.out,b25_select.out,arm_report.out,grip_arm_tally.out,smoke_*.log,grip_*.launch.log,grip_arm.driver.log}`
- 结果: `ws4_migrate/rep_ext_cfg/rep/out/b25_*/`（12 格注入）+ `fixE_tally.csv`；冒烟存档 `out_ws4b_smoke/`；W4a 输出存档 `out_ws4a_snapshot/`
