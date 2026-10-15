# RESULT — menagerie G1（g1_with_hands.xml）pads-only 变体（worker ws1b, TASKID=20261008-221515-qoder-03c4673f）

## 1. 结论（3 行）
1. **pads-only 隔离无法让该资产抓住方块**：20/25/35/40/50mm × {ti, tm} × {μ=1.0, μ=2.0} 共 **128 跑抓取 0 成功**（judging 与 W1 完全一致，未放宽任何门）。
2. 但**指节幽灵化确实改变了失败机制**（相对 W1 原装）：W1 原装是"释放瞬间脱手、抬升期零接触"；pads-only 在闭合期就有真实 pad 承载（接触力峰值 3.6 → **32.2N**），**释放后 100% 的 run 都有 pad-方块持续接触**（最好臂 tm2/40-50mm 平均持续 **656-815 步 ≈ 1.3-1.6s**，覆盖整个 hold+lift 窗口），release_slip 从 W1 的 **63-80mm 收敛到 4.6-10.9mm**（最好 5 跑已过 5mm 门）。⇒ 隔离是"必要不充分"。
3. 剩余瓶颈=**几何楔**：index/middle 基座固定 ±28.5mm（指尖高差 57mm）、thumb 夹层，使任何二指捏合都是斜楔；pad 两接触点法向与重力正交分量小，抬升一开始方块就沿楔面滑穿（lift_max 恒 ≤4.2cm，门 10cm）。20-50mm 全部同一签名 ⇒ **无尺寸阈值可用**（50mm 甚至最好：楔越宽 pad 包角越大）。

## 2. 变体定义（pads-only）
- 基底：官方 g1_with_hands.xml sha256=`2d41a3c6783fbf9e17349608d9c2222d970163b1db315ce9f30c4a97631fc078`（与 W1/官方一致）
- 变体 XML：`model/unitree_g1/ws1b_scene_model.xml` sha256=`9b577945d9de55536ec17f6cfa4323e09aded4dd41f71277a7d202899e6cccfd`
- 改法（只在右手 `<body name="right_wrist_yaw_link">` 段内做，8 个碰撞 geom 幽灵化 contype=0 conaffinity=0）：
  `right_hand_palm_link`(mesh)、`thumb_0`(mesh)、`thumb_1`(**box 0.01×0.015×0.01，即 20×30×20mm 代理体≈指节一半长**)、`thumb_2`(mesh)、`middle_0/1`(mesh)、`index_0/1`(mesh)；腕部 link 自身碰撞不动。
- 新增指尖 pad 球各 1（挂在远端 link，r=5mm，center=顶点-0.7r·tip_dir ⇒ 尖端外露 1.5mm；condim=4、density=0（运动学不变）、friction 主臂=资产默认 `1 0.005 0.0001`、μ2 臂=2.0）：
  thumb `ws1b_pad_thumb`、index `ws1b_pad_index`、middle `ws1b_pad_middle`。
- **改后每指保留的碰撞 geom 清单**：thumb=[ws1b_pad_thumb]，index=[ws1b_pad_index]，middle=[ws1b_pad_middle]，palm=[]（无）⇒ 右手唯一承载几何=3 个 pad 球（"只有 pad 承载"）。
- 记录全量见 `out/probe/pads_variant_record.json`。

## 3. 结果表（n/success；视频 run 不计入）
| 臂 | e20 | e25 | e35 | e40 | e50 |
|---|---|---|---|---|---|
| ti (μ=1) | 0/10 | 0/10 | 0/10 | 0/8 | 0/8 |
| ti2 (μ=2) | 0/10 | -- | -- | -- | -- |
| tm (μ=1) | -- | 0/10 | 0/10 | 0/8 | 0/8 |
| tm2 (μ=2) | -- | 0/10 | 0/10 | 0/8 | 0/8 |

对照（同一 harness）：**ideal 正对照 28/28 全过**（lift 0.20-0.38m、frac 0.90-1.00）；**negctl 负对照 0/36 如期全败**（手指不闭合；全部 no_lift）。⇒ §5A.2 分支证明成立：成功分支可达 + 必须失败分支真失败。

明细（均值，节选；全量 success_table.csv 128 行）：
| 配置 | release_slip_avg | release_drop_avg | 闭合期 pad 接触力峰值 | 释放后 pad 接触步数(avg/max) | 抬升期 frac_avg | fi_avg | lift_max_avg |
|---|---|---|---|---|---|---|---|
| e20 ti μ1 | 79.2mm | 77.0mm | 3.6N | 40 / 43 | 0.00 | 0.00 | 7.9cm |
| e20 ti2 μ2 | **4.9mm** | 7.4mm | 1.0N | 438 / 441 | 0.04 | 0.41 | 0.9cm |
| e25 ti μ1 | 74.5mm | 72.6mm | 5.2N | 68 / 261 | 0.00 | 0.00 | 7.4cm |
| e25 tm μ1 | 35.7mm | 43.2mm | 0.5N | 23 / 27 | 0.00 | 0.00 | 4.3cm |
| e35 tm μ1 | 43.1mm | 41.7mm | 21.1N | 259 / 323 | 0.15 | 8.0N | 4.2cm |
| e35 tm2 μ2 | 40.3mm | 41.5mm | 3.1N | 496 / 530 | 0.38 | 4.1N | 4.2cm |
| e40 tm2 μ2 | 10.9mm | 17.3mm | 6.7N | **808 / 823** | 0.41 | 4.9N | 1.7cm |
| e50 tm μ1 | 7.5mm | 15.4mm | **32.2N** | 656 / 682 | 0.26 | 13.7N | 1.5cm |
| e50 tm2 μ2 | 8.8mm | 16.3mm | 12.4N | 777 / 815 | 0.38 | 7.1N | 1.6cm |

失败原因直方图：**no_lift 128/128**。最接近门的 5 跑（e20 ti2 μ2 seed 001/004/006/007/009）：release_slip=**4.61mm（<5mm 门通过）**、reldrop 7.6mm、抬升期仍有 4% 接触，但 lift_max=9.4mm ≪ 100mm ⇒ 仍判 no_lift（未放宽）。

## 4. 与 W1 原装对照
| 项 | W1 原装（整手凸包） | pads-only（本工作） |
|---|---|---|
| 抓取成功率 20/25/35 | 0/45 | 0/60（ti/tm×μ1/μ2 各 10）+ 40/50 共 0/128 |
| 释放后 pad-方块接触 | 0/45（释放即自由落体，30ms 内脱手） | **128/128**（最好臂持续 1.3-1.6s） |
| release_slip | 63-81mm | 4.6-10.9mm（最好臂）/ 4.9mm 单跑最小 |
| 闭合期接触力 | 0.2-2.7N（跟踪滞后） | 3.6-32.2N（pad 真实挤入 1-17mm） |
| 抬升 lift_max | ≈0（恒 0.000） | 0.9-7.9cm（有握持但滑穿） |

⇒ **改善是真实的、可量化的，但不足以过门**。W1 记录的根因①（三指固定高差⇒上下面夹持/楔形）在 pads-only 下**依旧成立且成为唯一瓶颈**；根因②（指节顶开方块）被消除（幽灵化后无指节接触，见闭合期接触全部来自 pad）。

## 5. 机制（全部实测）
1. **pad 会真握**：闭合期 pad 挤入方块 1-17mm，接触力 3.6-32.2N（e50 tm：32.2N），释放后接触持续 438-815 步（0.88-1.63s）——指节幽灵化后"pad 承载"成立。
2. **斜楔弹射**：ti 深座（λ_g≈0.2-0.28）闭合期把方块沿楔面顶起 3-5.5mm（weld 软夹具被拉出 2.4cm 级位移可观测），释放后方块沿楔面滑出；e20 ti μ1 的 release_slip（79mm）反而比 W1（63mm）更差 ⇒ **深挤不是解**。
3. **浅座 tm + μ2 才接近门**：tm 座（λ_g≈0.48-0.65，挤入 0.2-1.7mm）+ μ=2.0 时 hold 段几乎不滑（4.6-8.8mm），但抬升加速度一来就滑穿（lift_max 恒 ≤4.2cm）。
4. **无人能三指抱**：任何 λ 下第三指 pad 距方块 21-110mm（index/middle 高差 57mm 的硬几何）⇒ 永远是 2 点捏，抗倾覆/抗滑移只靠 2 个接触点+摩擦锥。
5. **50mm 反而最好**（楔宽使 pad 包角大、32N 接触、contact 覆盖 0.94-1.16s）⇒ 结论不是"尺寸不够大"，而是"捏合方向错"（楔面与重力方向太近）。

## 6. 协议与偏离声明（判据零改动）
- 判据/阶段/门（lift≥0.10m、slip<5mm、≥1 个 pad-方块接触 >0.02N、无 weld）**逐字沿用 W1**；negctl/ideal 双对照保留。
- 偏离 1（**落座重标定**）：W1 的 placement.json 属整手凸包模型；实测（`out/probe/pads_calib.json`）在 W1 落座点 pads 全程无法接近方块（>0.5mm，e20）——原凸包捏合发生在远端 link **侧面**而非指尖。变体按"pad 收敛点"重新落座（同 ws1_place v3 手法：两 pad 轴平衡+审计臂 squeeze/clr0），表见 `out/probe/placement_pads_{ti,tm}.json`。
- 偏离 2（**审计姿态=稳定姿态**）：5mm pad 需要真实仿真姿态——实测手臂重力下垂 shoulder_pitch +0.0133rad≈手位 12mm，导致 λ_touch 差 0.07（0.20→0.34）；runner 先做 650 步 settle 探针（手指张开、不碰方块）再用该姿态做 spawn 审计与 λ_touch 扫描（W1 用指令姿态；这是我方修补，非判据）。
- 偏离 3（**夹具参考系**）：场景里烘焙的 cube 初始位姿=weld 的编译期参考；换了落座 P 但场景不快照会让 weld 把方块拉回烘焙点（实测 2.4cm 误差，首次冒烟全空）。故每臂场景由同一 placement 文件生成（ws1b_scene_<edge>mm_{ti,tm}.xml），与 W1 做法一致。
- 偏离 4（**ideal 粘连参考系**）：自检用"方块粘手"的参考系取**稳定姿态**（否则粘住的方块脱离 pad 捏合区，frac=0.00 假阴性）；修复后 ideal 28/28。
- kp：全部跑资产原生 **kp=500**（未动；W1 已证 kp100 无差别）；μ 只在 μ2 臂运行时覆盖（每 run runtime_stamp.pad_mu_override 记录）。
- 资源：≤8 并发、nice 10、OMP=1、RLIMIT_AS 16GiB、PYTHONDONTWRITEBYTECODE=1；渲染走 osmesa 配方（与 W1 相同 LD_LIBRARY_PATH）。

## 7. 产物（绝对路径）
- 本报告：`/data/group4/20261008-221515-qoder-03c4673f/ws1_menagerie/pads_variant/RESULT.md`
- 表：`.../pads_variant/success_table.csv`（192 行含对照；抓取 128 行）、`out/probe/final_summary.txt`（第 3/4 节原文）
- 变体：`.../model/unitree_g1/ws1b_scene_model.xml` + `out/probe/pads_variant_record.json`（改法/保留清单/全 sha）
- 标定：`out/probe/placement_pads{,_ti,_tm}.json`、`pads_calib.json`
- runs：`out/runs/`（192 run JSON + traj.npz + log；tag 前缀 vid_ 为视频 run）
- 视频：`video/e50_tm_grasp_seed0.mp4`（失败例，最长握持 32N）、`video/e35_tm_grasp_seed0.mp4`（失败例）、`video/e20_ideal_selfcheck.mp4`（ideal 正对照=成功分支）；每段带 `*_runtime_stamp.json` + 4 张关键帧 PNG
- 脚本：`scripts/ws1b_{lib,make_variant,make_scene,place_pads,calib_pads,run,matrix,diag,report,summary_final}.py` + `scripts_w1_ref/`（只读复制的 W1 原件）
- 流水：`/home/group4/group4_dasc7606c/logs/20261008-221515-qoder-03c4673f/steps-ws1b.md`
