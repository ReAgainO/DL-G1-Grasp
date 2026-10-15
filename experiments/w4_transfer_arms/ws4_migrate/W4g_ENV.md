# W4g_ENV.md — 掌托/包络式（envelope）抓取：实现与实验（第三棒收口）

父 TASKID: 20261008-221515-qoder-03c4673f（ws4g 子代理；三棒流水，本文件为终稿）
节点: worker00039 | 工作根: /data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/ | 臂: rep_ext_env
本文件配套证据：ws4g/（脚本+out）、rep_ext_env/{raw,rep/out,fixE_tally.csv}、video_env/、logs/（steps-ws4g.md 全程流水）

## 0. 结论摘要（先给结论，后附证据）

1. **两处实改（用户指令）均已实做、标注变体、一键可回退**：
   - A 尺寸守卫：edge 10..50→10..130mm、half 4..30→4..65mm（三文件），环境开关 `W4G_ENV_GUARDS=0` 精确回退。
   - B 碰撞配置：`right_hand_*` 遮蔽循环参数化 `--envelope-collision 0/1/2`；档1=远节三件（thumb_2/index_1/middle_1），档2=全链；档位生效有模型实读+接触审计数字。
   - 口径修正：**掌面 mesh 一直在碰撞（c1a1，位于 right_wrist_yaw_link、在遮蔽循环之外）**；"只有 3 pad 有碰撞"不完整；被遮蔽的只是 right_hand_* 链。
2. **三合一 rep_ext_env 建成**：双路由（cfg×PD/phys 两方向三路合并）**逐字节相同**；冒烟 a（全开关关）与 W4a 基线**全数组逐位同**；冒烟 b（注入默认配方=恒等 noop）全数组逐位同且 `identity_noop=true`。
3. **包络"拳上罩/拳握笼"构型已找到并定构型**（v5c 搜索 + FK/接触审计）：80mm q=[0.42,-0.2,-0.8,1.7,0.05,1.7,0.05]；100mm q=[0.4188,-0.0826,-0.9816,1.648,0.2547,…]；档1 接触=指垫/远节浅接触（-1.3~-3.9mm 级），无掌/腕/桌接触。
4. **实验 11 格：2 成功（均为基线口径回归格）+ 9 失败**；失败签名两分，且**机制已隔离**：
   - 拳握构型在 80/100mm **未通过 approach planner（静态支路搜索全拒，17.6s）**——planner 的 hand 可行域是捏合假设（指垫须能达到对置面 ±(s+r-0.5)mm）；
   - 捏合型大 span 注入（对照格 d80env_pinch）**通过静态搜索（static_feasible=true）、死在 alignment timeout（127s）**——与 W4f 常规 80mm 第一格同签名；
   - 35mm 拳握在 CLOSE 阶段"两指接触超时"（指垫悬空 1.7~16.5mm 未建立对置接触）。
   ⇒ 包络物理阶段未达；阻断点=planner 捏合假设 + alignment（小方块口径 contact_frame 失真）。下一步（方块预置掌心，W1 式）评估见 §8。
5. 120mm：按计划仅当 100mm 成功才跑——未跑（100mm 全败）。

## 1. 臂与基线

- rep_ext_env = rep_ext_comb（W4e 的 PD+phys 合并臂）再叠加 cfg（W4b 注入通道）六 opcode；对照基线 = rep_base（W4a 口径）。
- 冻结 flags、桌面/方块几何、45 项红门判据全部不动；一切新增均为 env 注入（`.flags_flat` 逐字节不变，sha 31d3d775… 与 rep_base 相同）。
- 运行器 run_fixE.sh（env 臂版）新增三枚 env 钩子：`ENVELOPE_COLLISION`、`GRIP_TARGET_JSON`、`W4G_ENV_GUARDS`，并写进每格 meta。

## 2. 三合一（双路由逐字节）与冒烟 a/b

- 三路合并用 git merge-file 机械做双路由：
  R1=merge(comb,base,cfg)、R2=merge(cfg,base,comb)；仅 2 处冲突（run() 签名尾、argparse 相邻行），
  resolve.py 归一化为同一解后 `cmp R1 R2` **逐字节相同**。核对：comb→R1 diff=恰 5 个 cfg opcode（无 PD/phys 丢失），cfg→R1 对称。
  存档：`worker-ws4g/diffs/comb_cfg_full.diff`（207 行）、`diffs/env_vs_comb.diff`（151 行）。
- **冒烟 a**（格 b25_12_04__env，envlvl=0、三开关全关，rc=0 wall=145s）：vs rep_base/rep/out/b25_12_04，
  qpos/qvel/body_reference/hand_reference/wrist_target/decoded*/applied_motor_target/actuator_ctrl/time
  全部 **bitwise=True max|d|=0.000e+00**；phase 序列同；result success/lift=0.12130220705160244/slip=0.0042366950878734945 逐位同；gates identical。
- **冒烟 b**（格 b25_12_04__noop，注入内置配方 JSON，rc=0 wall=130s）：全数组同冒烟 a 的逐位判据；
  result.grip_target_json: `applied=false, identity_noop=true, adaptive_ik_bypassed=false, adaptive_hand_calls=111`（与基线一致）。
- **冒烟 c**（= d80env_00 首格）：注入包络构型 → `GRIP_TARGET_JSON … applied=true`（stdout 实读）+ `ENV_COLLISION level=1` 名录；见 §6。

## 3. 实改 A：尺寸守卫扩展（标注变体，一键回退）

原始行（保留在文件内注释"Original line for the record"）与现值对照：

| 文件 | 原逻辑 | 现逻辑（W4G_ENV_GUARDS=1） | 回退 |
|---|---|---|---|
| rep/sonic_grasp.py（scene_and_cal，edge 守卫） | `not 10.<=cube_edge_mm<=50.` raise 'Cube edge must be finite and 10..50mm' | `not EDGE_MIN_MM<=cube_edge_mm<=EDGE_MAX_MM`，`EDGE_MIN_MM,EDGE_MAX_MM=(10.,130.) if ENV_GUARDS else (10.,50.)` | W4G_ENV_GUARDS=0 → 原界+原报错文本 |
| rep/sonic_grasp.py（argparse 后校验） | `10<=a.cube_edge_mm<=50,'A3: cube edge domain is 10..50mm'` | 同开关的 10..130 断言 | 同上 |
| rep/grasp_geometry.py（contact_frame half 守卫） | `not .004<=half<=.030` raise '…4..30mm' | `_HALF_MAX_M=.065 if ENV_GUARDS else .030` | 同上 |
| rep/adaptive_hand.py（AdaptiveHand half 守卫） | `not .004<=self.cube_half_m<=.030` | 同上 4..65mm | 同上 |

- 见证：80mm 场景生成冒烟（envsearch/envverify/probe 三套脚本各自多次实际以 80/100mm 生成 scene.xml 并载入 MjModel 成功；矩阵 80/100mm 格全部越过守卫进入物理/搜索阶段）；回退见证：cbc= 不设开关时 25mm 冒烟 a 逐位同（25mm 在旧界内，界值本身未触发）。
- 变体范围声明：仅放宽 domain 上界；不改变守卫语义（仍要求有限、非负下界 4mm/10mm 不变）；50mm 以上场景在本臂内均为标注实验。

## 4. 实改 B：碰撞配置分档（标注变体，mp/opt 两级）

mask 循环前后对照（rep/sonic_grasp.py scene_and_cal 内）：

```python
# 原（单行，已在文件内注释保留）：
#   geom.set('contype','2' if geom.get('name') in core.PADS else '0');geom.set('conaffinity','0')
# 现（ENV-B 参数化；level 0 输出与原逐字节一致的属性）：
if geom.get('name') in core.PADS: pads → '2'/'0'
elif geom.get('group')=='1' or geom.get('density')=='0': 视觉 geom → '0'/'0'
else: enabled=(envelope_collision>=2) or (>=1 and body in ENV_L1_BODIES) → '2'/'0' else '0'/'0'
```

- `ENV_L1_BODIES={right_hand_thumb_2_link, right_hand_index_1_link, right_hand_middle_1_link}`（携 pad 的远节=指腹内侧）。
- 档位模型实读（envprobe，80mm 场景自产后载入）：
  - L0（基线）：#87 腕壳 c1a1、**#89 掌面 c1a1**、#96/#101/#106 三 pad c2a0 —— 共 5。
  - L1：+ #95 thumb_2、#100 index_1、#105 middle_1（c2a0）—— 共 8。
  - L2：+ #91 thumb_0、#93 thumb_1(box)、#98 index_0、#103 middle_0 —— 共 12。
- 运行期审计：run() 载入模型后打印 `ENV_COLLISION level=.. enabled=[…]` 并写 result['envelope_collision']（含 enabled_geoms 名录与 guard 扩档值）。
- **接触审计（相位精确位姿 + mj_collision 全列；先例教训要求的"每档接触对/穿透"数据）**：
  - 80mm 构型 L0：接触仅 thumb 垫 -1.38mm（ncon=14）；L1：+thumb_2 -3.27mm（ncon=15）；**无掌/腕/桌接触 → 未顶块**。
  - 100mm 构型 L0：0 接触；L1：+thumb_2 -2.56mm（ncon=14）。
  - 35mm 同族：L0 thumb 垫 -5.09mm；L1 +thumb_2 -6.59mm（标注：偏深）。
  - 旧候选（design/scan 大 span 族，用于反例）：span=124.5 行 L0 即 `掌面 hull -34.97mm`、thumb 垫 -1.11、index 垫 -6.03；L1 再叠 thumb_2 -26.8/index_1 -34.7/middle_1 -36.7 ⇒ **物理不可用**（该族之所以从未通过物理阶段的独立原因）。
- 口径要点（审计中发现）：`mj_geomDistance` 对 mesh 走**凸包**距离（保守），接触生成走**精确三角**——100mm 构型掌面 hull=-1.8mm 而实际 0 接触（凹面）。文档中"顶/不顶"一律以接触对为准。
- 幽灵近节说明：L1 下 index_0/middle_0 等近节仍可深穿（-6~-16mm）而无力学（遮蔽），属本臂既定实验口径（变体标注）；L2 会把这些打开（旧先例 20/20→7/20 的机制），本实验未用 L2。

## 5. 包络构型搜索与定构型

- v5（30k 随机 + 离线 cost）：失败——cost 的 n≈-y 项与 bbox 口径压制大 span 家族；v5b（5 维对称坐标下降）：目标过严（近节 ≥-2mm 使可行域≈空）+ wrist_rel 公式笔误。
- **v5c（生效版）**：目标= 指垫窗 [-3,+8]mm、远节 [-2.5,+1]、掌面 [-2,+4]、近节 ≥-35（幽灵）、桌 ≥-6、分离度 sep≥0.35s、wrist 高 ≥s+45。**收敛到"拳上罩/拳握笼"族**：span≈2-14mm 拳握，方块罩于掌下，远节浅接触。
  - 80mm top1 q=[0.42,-0.2,-0.8,1.7,0.05,1.7,0.05]：垫 [-1.38,+2.47,+4.98]、远节 [-3.9,+0.3,-1.3]（hull）、掌面 +9.2、桌 +25.4。
  - 100mm top1 q=[0.4188,-0.0826,-0.9816,1.648,0.2547]：垫 [+0.35,+5.67,+8.18]、远节 [-2.8,+1.9,-0.6]、掌面 hull -1.8（实际0接触）、桌 +29.2。
  - 35mm：同族最好仍有桌穿（-12.6mm）或 middle_1 -11mm；v5d 35mm 专项细化无法改进（该尺寸下"拇指+中指双侧浅接触"在同族内不可达）。35mm 前置验证改用与 80 同族拳握（可比性，标注）。
- 构型 JSON（ws4g/grips/grip_env35/80/100.json；格式 {"grip_target_rad":[7]}，与 W4b 注入通道同构）与 FK 复核（envverify：n/span/cf 平移、垫 rel/gap、三档接触对）已存档 ws4g_envverify.out、ws4g_envprobe_final.out。

## 6. 矩阵结果（fixE_tally 全列 + 红门 + 接触构成）

fixE_tally（ws4g_env_tally.py，BASE=rep_ext_env）总计 11 格：**success=2 / 全败=9**。

| 格 | 尺寸/位置 | 注入 | 结果 | lift/slip | 红门数 | 接触构成（审计） |
|---|---|---|---|---|---|---|
| b25_12_04__env | 25mm 0.2912,-0.1344 | 无(envlvl0) | **SUCCESS** | 121.3mm / 4.24mm | 0 | 3pad+掌腕(基线) |
| b25_12_04__noop | 同上 | 默认配方(noop) | **SUCCESS** | 121.3mm / 4.24mm | 0 | 同上（逐位同） |
| a35_00_06__env | 35mm 0.266,-0.1276 | 拳握+env1 | two-finger contact timeout | - | 13 | L1=8geom；拇指垫 -5.09/远节 -6.59；中/食指垫悬空 1.7/16.5mm |
| d80env_00..03 | 80mm (0.285/0.298)×(-0.138/-0.115) | 拳握+env1 | static search rejected ×4 | - | 11 | L1 审计：thumb 垫 -1.38、thumb_2 -3.27；未到物理 |
| d80env_pinch | 80mm 0.285,-0.138 | 捏合大span 对照 | **alignment timeout**(127s) | - | 11 | 该配置 L0 掌面 hull -35mm（旁证） |
| d100env_00b/01b/02 | 100mm (0.292,-0.138/-0.115),(0.30,-0.13) | 拳握+env1 | static search rejected ×3 | - | 11 | L1 审计：thumb_2 -2.56 |
| d100env_00/01 | 100mm x=0.290 | 拳握+env1 | rc=1(1s) 桌面守卫 | - | - | **浮点边界**：0.24+0.05=0.29000000000000004>x=0.29；重发为 00b/01b |
| （120mm） | — | — | 未跑（100mm 未成功） | | | |

- 逐格 stdout（GRIP_TARGET_JSON applied=true、ENV_COLLISION level=1 名录）在 rep_ext_env/raw/*.stdout.log；汇总 ws4g_env_summary.out；tally CSV=rep_ext_env/fixE_tally.csv。
- 视频：无成功格 ⇒ 不产"成功录播"；已渲 1 段包络最远格回放（a35_00_06__env，含 runtime_stamp 命名）`video_env/a35_00_06__env_run1009-0649.mp4`（double-panel 全场景+手部近景，供机制复盘）。

## 7. 失败机制（签名、数字、隔离实验）

- **M1 approach planner 的捏合假设**：静态支路搜索（7 候选 ARDY 支路一次静态 IK）对拳握构型 **7/7 全拒**（`static_feasible:false`，17.6s 即退），拒因=`capture/hand/limits/open-table filters`；对捏合型注入（d80env_pinch）**static_feasible:true**（raw stdout 实读）→ 说明拒的不是臂，而是 hand 可行域（AdaptiveHand 以 ±(s+r-0.5)mm 对置面为目标的面区目标，拳头配置够不到）。
- **M2 alignment timeout（80/100mm 的第二道门）**：d80env_pinch 过静态搜索后死在 `alignment timeout`（dur=55.3s）——与 W4f 常规 80mm 第一格同签名；机制=小方块口径的 pinch_center/contact_frame 在注入构型下平移（W4b@35mm 实测 14.4mm），80mm 对齐伺服收敛不了。
- **M3 CLOSE 两指接触门（35mm）**：拳握构型在 cf 放置下拇指垫压深（-5.09mm）而中/食指垫悬空（+1.67/+16.49mm）→ CLOSE 无法建立"两指接触"（two_fingers 红门）→ 超时。数字见 §4/§5。
- **M4 桌面浮点边界**：cube_x=0.290 被 `0.24+0.05=0.29000000000000004` 拒（rc=1, 1s）；同族格一律用 ≥0.2901。
- 结论性判断：**包络的几何构型可达（v5c+审计成立），物理阶段被"planner 捏合假设 + alignment 小方块口径"两段式阻断**；必须先绕过这两段（§8 下一步），否则任何包络构型都到不了 CLOSE 之后。

## 8. 下一步评估：方块预置掌心（W1 式）（不实跑，给改动点与成本）

目标：绕过 M1/M2 两段阻断，让方块以"已在掌心/掌托位"的初始条件进入 CLOSE-LIFT。三种递进方案（行号以 rep_ext_env/rep/sonic_grasp.py 现版为准）：

- 方案 A（最小、只改对齐目标，≈15-30 行 + 1 新 flag）：ALIGN 阶段的 arm 目标目前是 `targetpos=d.xpos[cube]`（:433/:442-443，`point()` :264 走 pinch_center/contact_frame）。改为读一枚 `--palm-seat-json`（复用 grip_target_json 的载入模式），把 ALIGN/DESCEND 目标设为"注入构型的掌心点"（FK 一次算出 palm face 中心+相对偏移）。守卫：仅当注入激活时允许。
- 方案 B（预置方块 + 直入 CLOSE，≈20-40 行 + 2 守卫）：scene_and_cal 里把 cube_body 的 pos 文本直接写为掌心位（现 :118-119 的 pos_text 分支），并在相位机跳过 DESCEND/ALIGN（现有 `--phase-clips` 机制可承载）；守卫=预置时刻手为 OPEN、CLOSE 起点用注入构型。
- 方案 C（W1 原样复刻）：按 W1 的"方块预置掌心"设计（本仓库 W1 记录）复刻预置+手开合序列；成本=1 格冒烟（≈3 分钟）+FK 复核脚本（已有 fk_cfg/envverify 可复用）。
- 风险与判读：预置必须用 OPEN 手先落位（避免预置穿插）；成功判据沿用 45 项红门；若 lift 通过而 slip 红，则验证"掌托摩擦承载"是否成立（方块质量仅 0.020kg，μ=2.0，承载需求极低）。

## 9. 变更/变体清单（全部标注项）

1. ENV-A 守卫扩档 ×4 处（§3 表）；回退 W4G_ENV_GUARDS=0。标注：文件内注释 + result['envelope_collision'].guards_env。
2. ENV-B 遮蔽分档 ×1 处（§4）；level 0 逐字节基线；档 1/2 为标注实验档；启用名录随 run 记录。
3. 三合一 cfg 通道（grip_target_json）——W4b 既有变体，本臂仅原样合并（恒等 noop 已证）。
4. 运行器 env 钩子三枚（ENVELOPE_COLLISION/GRIP_TARGET_JSON/W4G_ENV_GUARDS）+ meta 记录。
5. 注入构型 JSON（grips/*.json；35/80/100/env80pinch/default 五件）——全部为标注实验参数，不入 .flags_flat。
6. 搜索/审计脚本（ws4g_envsearch*.py、ws4g_envprobe.py、ws4g_envverify.py、ws4g_env_summary.py、ws4g_env_tally.py）——只读 rep 源；scratch 目录自清理。
7. 35mm 前置验证用"与 80 同族拳握"（非同尺寸最优）——显式标注。

## 10. 文件与 sha（自查）

- rep_ext_env/rep/sonic_grasp.py = 548821b95916c3458747323d583495b8ca5bad016b9fb570820ee5c7bb466706
- rep_ext_env/rep/grasp_geometry.py = adc49dabb048e2d5e73e411d6ac4ec8eb1f2c1332f0a22b1334bb01ec19d2027
- rep_ext_env/rep/adaptive_hand.py = 966bee1b9e922068ba6cd1dfa29aba7fb16b94abc9e15564563e8e94779aa060
- rep_ext_env/run_fixE.sh = f74f872621aa642b23c8d942cfeecf716d78e57241e92df9687a87f7d3b02a1a
- rep_ext_env/.flags_flat = 31d3d77548e91ce6deb2f93fff0df4afebb4d5c2d01c107e8080422795559d1a（=rep_base）
- 源对照：base sonic_grasp 1e2a8edd…、comb 574bc600…、cfg f668518a…；base grasp_geometry bbbfbde3…、adaptive_hand f35a8268…；comb run_fixE 2b2cc5ab…
- 本地草稿：E:\qoder\qoder-data\Documents\Qoder\2026-10-08\2aa25fb2\worker-ws4g\（env_build/ 含 r1.py/r2.py 双路由与最终文件、diffs/ 全 diff、tools/ 全脚本）
