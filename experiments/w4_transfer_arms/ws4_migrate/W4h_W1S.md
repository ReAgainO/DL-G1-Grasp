# W4h_W1S.md — W1 式「方块预置掌心」包络握持验证（终稿）

父 TASKID: 20261008-221515-qoder-03c4673f（子代理 ws4h；父已认领，未新建 claim）
节点: worker00039 | 工作根: /data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/
主臂: **rep_ext_w1** = rep_ext_env 的完整副本 + 4 处文件内标注变体（全部 W4H_PRESET_JSON env 门控）
本机草稿: E:\qoder\qoder-data\Documents\Qoder\2026-10-08\2aa25fb2\worker-ws4h\
配套: ws4h/（补丁/搜索/驱动/台账/审计 json）、rep_ext_w1/{raw,rep/out}（15 格证据）、logs/steps-ws4h.md（全程流水）

## 0. 结论摘要（先给判定）

1. **判定：包络构型「握持+抬升」未获干净成功（本预算内）** —— 但 W1 预置协议本身**全链路打通并逐级验证**：
   15 格实验里 **8 格走完全部相位**（SETTLE→CLOSE→LIFT→HOLD→RELEASE→SETTLE_RELEASE，fail=None），
   CLOSE 接触门在 0.5~1.0s 即由注入包络构型满足；红门从 16 降到 8。**卡点从 W4g 的
   「到不了 CLOSE」变成一个纯粹的力学问题：方块在 LIFT 中从指垫笼里滑脱**（最好一格 d80w1_12：
   抬升 23.0mm 后滑脱，hold 期无指垫接触）。
2. **最好一格（d80w1_12，whisper 摇篮）**：指垫 gap [-0.65,-0.14,-0.32]mm，**两根指垫以 n_z=1.00
   的正上法向托住方块**（支撑在 CoM 投影内），拇指侧向合围；FK 复核偏差 0.0004mm；CLOSE 门过；
   LIFT 中先随臂上升 ~8mm、再滑移，23mm 封顶后脱出。抬升尺=0.151m（臂升 15cm），承载需求
   仅 0.196N ⇒ **失败不是"力不够"，是指垫-方块接触在动态中失稳/滑移**（详见 §6）。
3. **路线选择**：按 W4g_ENV.md §8 走 **方案 C（W1 原样复刻）与 A+B 最小组合**：方块按 FK 算出的
   掌心席位预置（world-cube 临时焊缝夹具，LIFT 前释放）＋注入包络构型＋跳相位（SETTLE→CLOSE）。
   冻结 45 项红门、`.flags_flat`、场景几何全部未动；一切扩展为标注变体。
4. **本次新发现两个系统级坑（行号级、实测数字）**——它们对任何后续"预置/夹具"类实验都是前提：
   - **MuJoCo equality weld 默认 solimp 使其刚度仅 ~83 N/m**（2N 载荷下 24.1mm 垂坠；调 solref
     .002→.000002 完全无效；solimp=[0.9999,0.99999,1e-5] 后 0.033mm）。W1 式夹具必须带 solimp。
   - **kinematic_servo 在 CLOSE 对焊缝方块追 `contact_frame→cube` 会风积（windup）到 46N**；
     用现成 `--freeze-close`（`sonic_grasp.py` 冻结 CLOSE 参考）即可消除。

## 1. 臂与改动（全部标注变体，一键可回退）

- `cp -a rep_ext_env rep_ext_w1`（481M）；`run_fixE.sh` 的 BASE 重指 rep_ext_w1（防写他人臂），
  meta 增记 `w4h_preset_json=`。`.flags_flat` 逐字节继承（sha 31d3d775… = rep_base，实测）。
- `rep/sonic_grasp.py` 6 个补丁（全部锚点断言单次命中，diff 存 ws4h/sonic_grasp_w1s.diff，100 行）：

| # | 锚点（rep_ext_w1/rep/sonic_grasp.py 行号为终稿） | 内容 |
|---|---|---|
| P1 | :50 ENV_L1_BODIES 后 | 模块级 `W4H_PRESET=_w4h_preset()`（env=W4H_PRESET_JSON 路径） |
| P2 | :146 pos_text 分支 | cube 世界位可用 JSON `cube_pos` 覆盖；`<equality><weld name="w4h_cube_fixture" body1="red_cube" solref=".002 1" solimp="0.9999 0.99999 0.00001">`（P5 硬化） |
| P3 | :224 neq 断言 | `m.neq==int(fixed_base)+1` |
| P4 | :336-352 pinch 初始化内 | 预置席位块：手冻结 FK→cf、按 JSON 放块、`initial_cube` 重取（lift 基准=预置位）、FK 复核（`design_gaps_mm` 指垫-方块 gap 偏差 ≤0.4mm 断言） |
| P5 | P2 的 weld 行 | solimp 刚性化（见 §3） |
| P6 | P4 的复核块 | 支持 `design_gaps_mm` 模式（cube_pos 可偏离 cf，freeze_close 使 CLOSE 被动，安全） |
| P7 | change() LIFT 分支 | 释放焊缝（`d.eq_active[eq]=0`，记录 released_at_s）；CLOSE 分支可选提前释放 |
| P8 | 全相位 hand 赋值后 | `freeze_hand`：手冻结在注入构型（含 SETTLE） |
| P9 | SETTLE 转相 | `skip_to_close` 直跳 CLOSE；`settle_s` 可调（0.5s） |
| P10 | contact_log.end() 后 | `weld_active_steps_lift_hold` 审计（必须为 0） |
| P11 | 结果写入前 | `result['w4h_preset_seat']` 全量记录（含 fk_check、release 规则） |

（P 编号为叙述序；实际以 ws4h/w4h_patch*.py 六个脚本为准，锚点逐条断言。）

## 2. W1 式预置协议（本臂版）

预置 JSON 字段：`cube_pos`(world)、`arm_q`(7 右臂预姿态，替代 neutral 参考)、`weld`、`freeze_hand`、
`skip_to_close`、`settle_s`、`weld_release`(LIFT/CLOSE)、`design_gaps_mm`(FK 复核)。
运行序列：SETTLE(0.5~2s，手冻结、方块焊缝在掌心席位) → CLOSE(接触门 0.2s@≥2 指垫>0.1N 后) →
LIFT(R-角点释放焊缝；grip_frame_lift 垂直 +15cm) → HOLD 2s → RELEASE → SETTLE_RELEASE。
焊缝释放规则（结果内记）：LIFT/HOLD 全程 `eq_active=0`（`weld_active_steps_lift_hold==0`，实测全格=0）；
`no_external=true`（无外力注入）；承载只允许指垫类（envelope level 0 遮蔽＝R3 既定 pads-only 口径）。

## 3. 实测的两个系统级坑（任何后续预置类实验必读）

**(a) equality weld 是"软橡皮筋"**（ws4h_weldtest*.py + 台账）：
- 手装 weld `solref=".002 1"`（照抄 fixed_base 惯用值）：2N 静载垂坠 **24.145mm ⇒ 有效刚度 82.8 N/m**；
- solref τ 从 .002 到 .000002（4 个数量级）**垂坠完全不变** ⇒ solref 对 weld 无效；
- 唯 solimp 有效：默认 [0.9,0.95,0.001,0.5,2] → 24.1mm；[0.99,0.999,1e-4] → 0.335mm；
  **[0.9999,0.99999,1e-5] → 0.033mm**（采用值）；
- 后果（修复前）：指垫 1~2N 的按压即可把"焊死"的方块拽离席位 10~25mm，FK 席位设计全废
  （d80w1_09/10 的逐拍台账：0.10s 内方块自由落体式下沉 12mm 再回弹）。
**(b) CLOSE 期 kinematic_servo 风积**：servo 每 0.1s 用 `contact_frame→cube 中心` 的 IK 修正臂位；
对焊缝方块会把指垫越压越深（d80w1_04：指垫 46.2N 尖峰、min 垂直力 -43.5N，接触状态被冲散）——
用现成 `--freeze-close` 让 CLOSE 冻结在句首参考（`sonic_grasp.py` 现版行为，非新改），风积消失。
**(c) 起手冲量墙**：刚性焊缝 + 深压（-1.27mm 级）⇒ t=0 指垫尖峰 46~55N（d80w1_03/04/13），
指垫-方块接触在 0.3~1.5s 内被冲散；-0.6mm 级"耳语接触"尖峰 17N、稳态即 T 4.1N/I 1.4N 且持续
（d80w1_11 的 1s 稳态台账）⇒ **深压封顶 ≈0.6~0.7mm**。软 solref(0.02) 对深压有缓解但会削弱握持
（d80w1_15：抬升 0.2mm 即滑）。三个力的走廊：**weld 必须刚性、按压必须浅、CLOSE 必须冻结**。

## 4. FK 席位搜索（ws4h_seat/seat2/seat3.py，"掌心空腔中心"的求法）

- 席位定义：跑动时 ALIGN/CLOSE 的伺服平衡点=`contact_frame(opponent=middle)`（=中指尖-〔s·Σ|axis|+r-.0005〕·n，
  与 W4g envverify 的 cf 口径逐字一致），故 cube_pos=cf（seat3 起允许 cf+δ，配 freeze_close 被动 CLOSE）。
- 搜索空间与判据演进（全部实测数字留痕）：
  1. seat1（12k 家族普查）：**v5c 族是"上罩"**（三垫全在方块上方 −1.4/+2.5/+5.0，只有 1 垫接触 ⇒
     即便抬起，`two_fingers` 红门必红）；普查出 M 族（上/下跨夹）与 C 族（全垫在下=摇篮）。
  2. seat2（arm_q+hand_q 14 维，目标=≥2 垫 [-1.5,-0.3]+掌面≥0.3+身体/桌净空）：得"2 上 1 下"钳形
     （[-1.27,-0.34,+0.55]，relz [+46,+50,-48]）——但底部垫在下棱侧外，**非承载支撑**。
  3. seat3（+δ3 维=17 维；判据升级为**真实接触法向**）：要求 **≥2 指垫 n_z≥0.35 的正上支撑 + CoM
     投影落入支撑点凸包（≥8mm 余量）**+掌面/身体/桌净空。收敛到**摇篮**：指垫 [-0.65,-0.14,-0.32]、
     两垫 n_z=1.00、拇指 n_z≈0 侧围、span≈100mm、palm 35.7mm、body 117mm、table 64.4mm。
- 运行期 FK 复核（本臂 P4/P6）：按 JSON cube_pos 置块后实测指垫-方块 gap，与 `design_gaps_mm` 比对
  ——d80w1_12 实测 **偏差 0.0004mm**（=模型载入几何自洽的强证据）。

## 5. 实验矩阵（15 有效格；口径=fixE 红门全列 + 每格 result['w4h_preset_seat']）

| 格 | 变体 | 终局 | lift_max | slip(hold) | 红门数 | 备注（机制） |
|---|---|---|---|---|---|---|
| d80w1_00 | 中性臂+seat1 幽灵席 | CLOSE 两指超时 | 4.3mm | - | 13 | 席位近腿部：方块-大腿 other_robot 222N（预置位贴髋） |
| d80w1_03 | arm-free 钳形（软焊缝） | CLOSE 两指超时 | 0 | - | 16 | 拇指被 46N 冲量滑脱 |
| d80w1_04 | arm-free 钳形+焊缝 | **全程完成** | 4.4mm | 101.9mm | 10 | servo 风积 46N；LIFT 释放即脱手 |
| d80w1_05 | +提前释放(CLOSE) | CLOSE 两指超时 | 4.2mm | - | 14 | 释放后方块被挤出 |
| d80w1_06/07 | +freeze_close(2.0/0.5s) | CLOSE 两指超时 | 4.4/5.6mm | - | 15 | 冻结使按压不足门槛 |
| d80w1_08 | whisper 三侧笼 | fall/nonfinite | 12.5mm | - | 16 | 该臂位自身失衡（弃） |
| d80w1_09/10 | whisper 钳形+冻结（.002/.0002 焊缝） | **全程完成** | 0/0mm | 21.0/21.0mm | 10 | weld 软垂 12mm，席位失效，方块穿垫坠落 |
| d80w1_11 | +刚性焊缝(solimp) | **全程完成** | 0mm | 60.6mm | 10 | 稳态 T4.1/I1.4N 撑住 1s，释放后穿垫坠落（上罩族无下向支撑） |
| **d80w1_12** | **摇篮（2 垫 n_z=1.0 支撑）** | **全程完成** | **23.0mm** | 31.8mm | **8** | 先随升 ~8mm 后滑移；接触失稳（§6） |
| d80w1_13 | 深压钳形+刚性焊缝 | CLOSE 两指超时 | 0.4mm | - | 15 | t=0 尖峰 54.7N 冲散 |
| d80w1_14 | 摇篮+提前释放 | 全程完成 | 16.6mm | 80.8mm | 10 | 提前释放未改善 |
| d80w1_15 | 摇篮深支（-0.73）+软垫(0.02) | 全程完成 | 0.2mm | 38.3mm | 8 | 软垫削弱握持，立即滑 |
| d80w1_16 | （误用深带臂位 preset，相位 clip 断言即崩） | rc=1 | - | - | - | 作废格，如实列出 |

- 红门演进：首格 16 红 → 最好格 8 红。最好格的 8 红全部为**承载/落桌类**：
  `hold_7cm, two_fingers, no_support, clearance_4cm, slip_1cm, release_drop_6cm, final_table_supported,
  no_robot_table_contact_full_task`（最后一枚由臂-桌擦碰带来，复盘见 §6）。
- 视频：**无成功格 ⇒ 按协议不产"成功录播"**（W4g 同样处理）。

## 6. 失败机制（级别定位）

- **L1（已绕过）approach planner 捏合假设 + alignment 小方块口径**（W4g M1/M2）：跳相位+预置后
  不再经过（CLOSE 门 0.5~1.0s 通过、`GRIP_TARGET_JSON applied=true`）。
- **L2（已修复）夹具与伺服级**：见 §3(a)(b)(c)——weld solimp、freeze_close、浅按压三条，
  修复前任何席位设计都会被这三者之一打穿。
- **L3（当前卡点、力学级）**：**指垫笼在 LIFT 中的承载失稳**。逐拍证据（d80w1_12）：
  t=1.05 释放后方块随升 +7mm（t=1.30 cz 0.6142），随后 8s 内方块相对腕慢 15mm 并持续下滑
  （t=2.4 后 cz≈0.5967 平台，T/M 各 ~0.2-0.3N，index 支撑接触 1.05s 后即消失）；
  hold 期 `pad_loaded_steps=0`。即：**正上支撑接触只在释放瞬间存在，一进入动态即退化为
  0.2N 级的残余接触，不足以在 15cm 提升中保持抓持**。加深支撑（13/15）会被起手冲量或软垫
  反向破坏——存在参数走廊但本手 7-DOF 指系 + 该臂控制器下未找到兼顾点。
- **L4（口径级）`final_table_supported`**：预置席位必须在"净空区"（桌板之下/桌沿之前，x<0.24）
  才不撞桌；而该口径要求末态由**桌面**承载 ⇒ 释放落点在桌面之外（本次落地板）。
  这是"W1 预置协议 + 冻结落桌口径"的结构性错配（若要全绿须 SETDOWN 返桌或改落点口径——均超出
  本次"标注变体"边界）。
- **L5（附带）`actual_arm_speed_within_limit`/`no_robot_table_contact_full_task`**：起手 0~0.12s 的
  接触冲量与臂位姿瞬态所致（臂速 2rad/s 限被 t=0 瞬时超），随 L2 修复后可复查。

## 7. 与 W4g §8 的对照

| §8 方案 | 本次执行 | 结果 |
|---|---|---|
| A（对齐目标改掌心点） | 不需要：skip 相位后 ALIGN 不再经过 | 省 |
| B（预置方块+跳 DESCEND/ALIGN） | **已做**（P2/P9，`--phase-clips` 之外的独立 skip） | 成功绕开 M1/M2 |
| C（W1 原样复刻） | **已做**（world-cube 临时焊缝 + 预置掌心席 + LIFT 前释放；"手冻结"变体=标注） | 协议全通，力学未达 |
| §8 未预估 | **新增三个系统坑**（§3）：weld solimp 软、servo 风积、起手冲量 | 已分别用 solimp / freeze_close / 浅按压解决并留数字 |

## 8. 变更/变体清单（全部标注）

1. rep_ext_w1 = rep_ext_env 副本（481M）；BASE 重指 + meta 增列 `w4h_preset_json`。
2. sonic_grasp.py 6 补丁（§1 表；全部 W4H_PRESET_JSON 门控；未给该 env 时逐路径惰性）。
3. 夹具 weld `solimp="0.9999 0.99999 0.00001"`（标注：W4h W1S 刚性夹具；数字见 §3a）。
4. `--freeze-close` 经 run_fixE.sh 既有 W4C_PHYS 直通（meta `w4c_phys_args` 实录）。
5. 席位/构型 JSON 13 件（ws4h/presets、ws4h/grips，全部带 note 与审计数字）。
6. 脚本：ws4h_patch*.py(6)、ws4h_seat{,2,3}.py、ws4h_families.py、ws4h_open_audit.py、
   ws4h_weldtest{,2,3,4}.py、ws4h_mkpreset.py、ws4h_debug*.py、ws4h_drive.sh、jobs×10。
7. 35/100mm 扩展格未跑：冒烟未成，按任务书"若败：报签名+机制"执行（100mm 拳握构型 W4g 已证
   L1 仅 -2.56mm 单接触，同一力学卡点，预期不差于 80mm 但无新增信息）。

## 9. 文件与 sha（自查）

- rep_ext_w1/rep/sonic_grasp.py = 0bd9ea1b4e12cd387226bd6a25bdeb7fee23a10ca0f774f64fc8667bf11ce424
- rep_ext_w1/run_fixE.sh = cca67cf30cfa7b14e21b6ac2002dad13bda29c5d235126f17cfbd2039ff8f48f
- rep_ext_w1/.flags_flat = 31d3d77548e91ce6deb2f93fff0df4afebb4d5c2d01c107e8080422795559d1a（=rep_base，逐字节）
- rep_ext_w1/rep/grasp_geometry.py、adaptive_hand.py = 与 rep_ext_env 完全相同（diff -q 实测）
- 差分：ws4h/sonic_grasp_w1s.diff（100 行）、ws4h/run_fixE_w1s.diff（19 行）
- 证据：rep_ext_w1/raw/d80w1_*.{meta.txt,stdout.log,result.json}、rep_ext_w1/rep/out/d80w1_*/
  {result.json,telemetry.csv.gz,cube_contacts.csv.gz,scene.xml,trajectory.npz}、rep_ext_w1/progress.txt
- 汇总：ws4h/ws4h_matrix_summary.out、ws4h/seat{,2,3}_audit_80.json、ws4h/ws4h_weldtest*.py 输出在 logs/w1s.*.launch.log
- steps：/home/group4/group4_dasc7606c/logs/20261008-221515-qoder-03c4673f/steps-ws4h.md

## 10. 下一步建议（未做，如实）

1. **力学层**：要过 LIFT 需让指垫笼"锁住"。两个候选：(i) 双垫支撑再加一指垫构成三点**下托**（需要
   新的 hand 构型空间搜索，判据已就绪=seat3 的 n_z+CoM 凸包）；(ii) 接受"掌面承托"变体并同步
   重定义 `fingertip_only_robot_contacts_in_hold` 口径（属红门改动，须上层授权——本次未动）。
2. **落桌口径**：若要 45 门全绿，需 `--setdown` 返桌路径（flags 冻结，需授权）或明确"W1 预置协议的
   落点为净空区、不返桌"的口径注记。
3. 复用资产：本臂的预置/夹具/搜索/审计脚本对任何"预置掌心"类实验即插即用（含 weld solimp 经验值）。
