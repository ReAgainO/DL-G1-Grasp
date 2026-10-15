# RV_AUDIT.md — 独立审计（RV）

- 父 TASKID: 20261008-221515-qoder-03c4673f; 审计者: worker00039 上的子代理 RV（不新建 claim）
- 审计范围: W1 / W1b / W2 / W3 / W4a / W4b / W4b2 / W4c 的**产物重算**（从 result.json / trajectory.npz / telemetry.csv.gz / csv 原始件重算，不信 worker 汇总表）
- **不在范围**: W4e 组合臂（其目录/文件全程未读写）
- 纪律: 一切只读（未写任何被审目录；审计自有输出只在 `ws6_review/` + 本地草稿）；未用 sudo；未驱动其它 CLI agent；未跑任何仿真
- Step 0 身份门: `ssh S4000 'hostname; date'` ⇒ `worker00039` / `2026-10-09 00:04:50`, rc=0 ⇒ PASS（证明后续读到的是目标节点的目标分支）
- §5A.2 自证（目标分支证明）: 每项结论下都给出"我读到的具体文件路径 + 关键字段实测值"；所有重算脚本与输出留在
  `/data/group4/20261008-221515-qoder-03c4673f/ws6_review/rv_scratch/`（`rv_recount.py/.out`、`rv_smoke.py`、`rv_smokeA_w4b.out`、`rv_smokeB_w4b.out`、`rv_smokeA_w4b2.out`、`rv_smokeA_w4c.out`、`rv_smoke_c20d.out`、`rv_smoke_phys2.out`、`rv_mp4frames.py/.out`、`rv_w4c_metrics.py/.out`）

---

## 0. 审计表（项 / 方法 / 结论 / 证据路径）

| # | 项 | 方法 | 结论 | 证据路径（关键字段实测值） |
|---|---|---|---|---|
| 1a | W4a 基线 5 格 | 自写 `rv_recount.py` 直读 5 个 `result.json`；再与 S1000 源同格对拍（自写 `rv_smoke.py`，NaN-aware 逐位） | **PASS** | `rep_base/rep/out/b25_*/result.json`：success=2（`b25_04_01` lift/hmin=0.1440/0.1238、`b25_12_04` 0.1405/0.1213，red=[]）；近成功 2 格 red=`[no_robot_table_contact_full_task]`（00_00 133.0/3.62、02_06 121.5/3.69）；`b25_00_10` = two-finger contact timeout / 13 门红。S1000 同格：success 与 red 集合**5/5 全同**；fb=0 的 3 格（12_04/02_06/00_10）**全数组逐位相同**（max\|d\|=0）；04_01（fb=30）hand_reference 逐位同、qpos 后段 max\|d\|=2.176e-2；00_00（fb=42）微移（lift 0.1441 vs 0.1442）|
| 1b | W4b 注入臂 12 格 | 直读 12 个 `result.json`；统计 fail 分布；与 rep_base 同格 + S1000 源格对比；复查注入通道证词 | **PASS（附口径限定）** | `rep_ext_cfg/rep/out/b25_*/`：**success=0/12、legacy_success=0/12**；fail 分布实测 = 7× two-finger contact timeout + 4× alignment timeout + 1× 跑完全程 = 12（与报告一致）。2 个基线成功格 `b25_04_01`、`b25_12_04` 均 → `fail_reason=two-finger contact timeout`（gates 12 红）。8 个新格 S1000 源基线核对**逐格全中**（00_18 -0.09/21.92、02_09 -0.09/15.88、04_04 -0.09/46.77、10_18 -0.09/15.73、10_19 -0.09/20.26、12_05 -0.09/18.05、12_10 -0.09/26.49、12_14 -6.06/151.29）。注入确实生效：12/12 `grip_target_json.applied=True`、`adaptive_ik_bypassed=True`、`adaptive_hand.calls=0`（对照基线 calls=111/143）|
| 1c | W4b2 位置伺服 9 格 | 直读 9 个 `result.json`；逐格与基线（rep_base / S1000 a35 层）对比；核对 fb 与 finger_control 落盘 | **PASS** | `rep_ext_pd/rep/out/`：success=3（`a35_00_06` 122.1/2.76、`a35_00_10` 128.9/2.91、`b25_02_06` 131.7/2.25），与报告 tally `total=9 success=3` 同。b25 **3 升**：02_06 F→T；00_10 timeout→lift 134.9（1 红）；00_14 从未抬起→131.8（1 红）；**3 降**：00_00 →7 红（-0.1/19.51）、04_01 T→F（127.1/2.66）、12_04 T→two-finger timeout。35mm 3 格：a35_00_06 T→T（slip 3.80→2.76）、a35_00_10 F→T、a35_00_15 -0.1/20.55→134.1/2.76（仍 1 红）。PD 侧 fb 实测=报告值（02_06=18、00_10=22、00_14=0、04_01=17、00_00=48、12_04=0、a35 全 0）；`finger_control` 9/9 落盘 mode=position kp=100 kd=10 armature=0.1，冒烟A 侧为 mode=torque/bypass=true；max/mean/sat=0.1909/0.000920/0.0015（=报告的 0.191/0.00092/0.15%，取自 a35_00_06）|
| 1d | W4c 物理配方 27 臂 | 直读 27 个 `result.json`（`<格>__<臂>`）；按 arm 分组统计；自写 `rv_w4c_metrics.py` 复算 2pad/HOLD 与 ΣF_min | **PASS（附口径限定）** | `rep_ext_phys/rep/out/`：27 = base 10 + phys 10 + phys2 1 + soft 3 + sub4 3。25mm 6 格 **base 2/6 → phys 3/6（strict success）**；唯一 strict 翻转格 = `b25_00_00`（15.25N 真桌接触→0 红，134.1/0.62）；"抓住（≤1 红）"4/6→6/6（00_10→138.2、10_17→135.3）。20mm 4 格 **base 0/4 → phys 0/4 strict success，但 0/4 → 3/4 legacy 抓住**（c20d_10_03 136.3/0.71、c20d_12_03 143.9/0.76、c20f_09_01 144.1/0.70，均只余 1 红；c20f_06_19 反向 1.0/32.9）。slip 降幅逐格复核：3.62/3.78/4.24/3.69/150.31 → 0.62/0.54/0.51/0.97/1.36（25mm），20mm 0.70–0.76。独立复算 2pad/HOLD：c20d_12_03 82/1000→980/980（ΣF_min 0.0→0.9879）、b25_10_17 664/980→980/980（0.0→0.1723）、c20f_06_19 phys 0/980 —— 与报告**逐值相同** |
| 2 | 逐位同 / bitwise 断言 | 不用 worker 脚本，自写 `rv_smoke.py`（严格列出"仅 A 有/仅 B 有"、shape/dtype、NaN 计数、NaN-aware 逐位）对 4 组冒烟 + 扩展对拍全部重跑 | **PASS** | (a) W4b `out_ws4b_smoke/a_noflag_b25_12_04/b25_12_04` vs `rep_base/rep/out/b25_12_04`：12 个物理数组 `bitwise=True max\|d\|=0.000e+00`（另 2 个差异键=`scene`/`runtime_stamp`，是路径/时间戳元数据，不在断言面）。(b) `b_default_b25_12_04` vs (a)：**全部数组含 scene/runtime_stamp 逐位同**；`applied=false, identity_noop=true`。(c) W4b2 `rep/out_bypass_smokeA_keep/b25_12_04` vs rep_base：12 数组逐位同；`wrist_target` NaN 计数 2430=2430 且 both_nan 完全重合、非 NaN 2217 值全等 ⇒ "DIFF 是 NaN≠NaN 伪影"成立。(d) W4c `b25_12_04__base` vs rep_base：12 数组逐位同；**20mm `c20d_10_03__base` vs S1000 源整目录对拍全数组逐位同**（14/14，含 qpos/qvel/actuator_ctrl/hand_reference），且两 run 分属不同时间（__base 23:30 vs 源 13:45）、scene 路径串不同长度（<U103 vs <U78）⇒ 是**跨目录跨次复现**，不是拷贝。(e) `b25_00_00__phys2` vs `__phys` 逐位同（确定性）。无"假绿"：所有被比目录的 result.json sha、mtime、scene 绝对路径两两不同 |
| 3 | 视频与成功对应 | 帧数用自写 ISOBMFF 解析器 `rv_mp4frames.py` 数 sample（节点无 ffmpeg/ffprobe）；sidecar json 逐字段与源 result.json/npz 断言；视觉抽查 2 帧（拷到本机用 Read 看图）；用红块像素面积比反证"没拿错格" | **PASS** | `video_pd/W4b2_pd_a35_00_10.mp4`=745 samples=ceil(1489/2)、`..._b25_02_06.mp4`=746=ceil(1492/2)，PNG 中间件 745/746 张；源格 result.json lift/slip/success=128.9/2.91/True 与 131.7/2.25/True，逐项与 README 相同。`video_phys/*.json` 3 个 sidecar 与源格断言 **3/3 MATCH**（含 gates_red 集合、frames=源 qpos 长度 1513/1549/1530），mp4 samples=ceil(frames/4)=379/388/383。W1 `video/e20_grasp_0.mp4`、`e20_negctl_0.mp4`、W1b `e35_tm_grasp_seed0.mp4`、`e20_ideal_selfcheck.mp4` 各 107 samples = stamp `n_frames=107`（源 traj 2050 拍/25Hz≈107 帧）；W1b `variant_model_sha=9b577945…` 与磁盘 `pads_variant/model/unitree_g1/ws1b_scene_model.xml` sha **实测相同**。视觉抽查：a35_00_10 与 b25_02_06 第 600 帧均见 G1 手内夹持红色方块；红块像素线性尺寸比 1.49（=35/25=1.40 量级，第 100 帧 39px vs 27px）⇒ 两视频确为 35mm 与 25mm 两格，未串格 |
| 4 | runtime_stamp 完整性（§17） | 逐产物 dump stamp 键集（AGENTS.md sha256=9e2c073c…，§17 要求 7 项：mujoco_version / sys_executable / python_version / model_sha / scene_generator_sha / library_sha / timestep-dt） | **PASS（2 处语义缺口，见问题 1/2）** | W4 线所有抽查产物（rep_base、rep_ext_cfg、rep_ext_pd、rep_ext_phys 各臂）stamp **8 键齐全**，含 `dt`；`scene_generator_sha` 与各臂代码 sha 一一对应（base 1e2a8edd / W4b f668518a / W4b2 5d1bac78 / W4c 45f0c6d8），可区分臂。W1/W1b 每视频/每 run 有独立 stamp json（含 dt=0.002、model_sha=2d41a3c6…、scene_generator_sha、sys_executable、python_version、scene_sha256），**无 `library_sha` 键**（该线无外部位姿/权重库，影响低）|
| 5 | W2 构型 7 中位数 | `python` 一条命令直读 `ws2_dataset/grasp_configs.csv`（sha256 751d4e4f…）重算 | **PASS** | n=118 行；成功集 = `excluded==0` = `episode<=80` = **81 行**；7 个 `cfg_hold_final_*` 中位数与 FINDING.md §5 **逐项差 0.0000**：-0.9738/-1.4879/-0.9594/-1.4810/+0.0151/+0.6207/+0.6749。旁证：W4b 注入向量 `[-0.0151,-0.6207,-0.6749,0.9594,1.4810,0.9738,1.4879]` 正是该 7 值的右手镜像（符号逐项核对通过）|
| 附 | W1b 断言的计数面 | 直读 `pads_variant/success_table.csv` 过滤 `variant=pads-only` | **PASS** | pads-only 共 195 行，其中 `mode=grasp` 130 行、**success=0**；扣掉 2 个视频 run（e35_tm/e50_tm seed0）后 = **128 跑 0 成功**，与 RESULT.md 表内 46+10+36+36=128 分毫不差 |

---

## 1. 问题清单（描述 / 证据 / 影响 / 建议）

### P1（中低）`runtime_stamp.dt` 对 W4c 启用臂是**过时值**——记为 0.002，实际积分步长 0.0005
- 证据：`rep_ext_phys/rep/out/b25_12_04__phys/result.json` → `runtime_stamp.dt=0.002`，而同一 JSON 的 `physics_recipe_w4c.physics_timestep_s=0.0005`（stdout 亦有 `W4C_PHYSICS {...physics_timestep_s=0.0005...}`）。`__sub4` 臂同样。
- 影响：§17 要求 stamp 含 timestep/dt；只读 `runtime_stamp` 的下游会把"物理配方臂"误读成与基线同 dt。这是 §17 立条针对的"版本/参数敏感性"同类。
- 建议：主报告引用 W4c 数字时把 dt 写成 **0.0005（4 子步）**，出处用 `physics_recipe_w4c`，不要引 `runtime_stamp.dt`；后续臂建议把生效 dt 写回 stamp。

### P2（低中）`model_sha` 不覆盖运行期模型/求解器改写
- 证据：W4b2 的 9 格在载入时把 7 个手指关节 armature 0.01→0.1，但 `runtime_stamp.model_sha.robot` 与基线同（8f00ac7a…，rep_ext_pd 内 base/pd 一致）；W4c 的 phys 臂 impratio/margin/solref 也是运行期改写，`model_sha` 不变（86713c23…）。
- 影响：单看 stamp 无法分辨"同一模型不同物理臂"；但臂身份可由 `scene_generator_sha` + `finger_control` / `physics_recipe_w4c` 恢复，故可接受。
- 建议：引用时把"生效开关"与数字同列（W4b2 写 `kp100/kd10/armature0.1`；W4c 写四件套）。

### P3（口径，最重要）"20mm 0/4→3/4" 不是"成功"口径，是 legacy 抓握口径
- 证据：`c20d_10_03__phys` / `c20d_12_03__phys` / `c20f_09_01__phys` 三格实测 **success=False**（各余 1 红：`no_robot_table_contact_full_task` 或 `final_table_supported`），仅 `legacy_success=True`（HOLD 两指 980/980）。W4c 报告本身写得很清楚（§0"3/4 抓住"、§4.2"仍是 0/4 成功"）。
- 影响：若主报告写成"20mm 失败 3/4 可翻为成功"，即为夸大。
- 建议：主报告必须写 **"20mm：strict success 0/4→0/4；抓握（HOLD 两指成立）0/4→3/4"**；同理 "25mm 2/6→3/6" 是 strict success（可直接引）。

### P4（口径）W4b"恶化 12"中 8 格没有 rep_base 同格基线
- 证据：12 格中仅 00_10/02_06/04_01/12_04 在 rep_base 有同格；另 8 格的"基线"来自 S1000 全层归档（我已逐格核对数值全对）。
- 影响："恶化 12"若被读成"12 格都有同格 A/B 对照"会高估证据强度（这 8 格是"跨批次基线 vs 今夜注入"）。
- 建议：写成"12/12 恶化（4 格有 rep_base 同格复跑；8 格对照 S1000 归档格，数值已核）"。

### P5（低）W4b2 §3 表 `a35_00_15` 基线红门列举不全
- 证据：报告写 `[hold7cm,two_fingers,no_support]`，实测该格 6 红（另有 `clearance_4cm`、`release_drop_6cm`、`slip_1cm`）。
- 影响：仅列举不全，不改结论（"从未抬起"仍成立）。
- 建议：引用时用"6 红（含 hold_7cm/two_fingers/no_support）"。

### P6（低）"35mm 3/3 改善"含 1 格"保持成功"；strict success 实为 1→2
- 证据：a35_00_06 T→T（lift 128.7→122.1，slip 3.80→2.76）、a35_00_10 F→T、a35_00_15 F→F(134.1)。
- 建议：写"3/3 干净对照：1 保持成功 + 1 翻全绿 + 1 从零抬起（降 slip），strict success 1→2"。

### P7（低）W4b2 的 b25_02_06"翻成功"带 fb=18 限定
- 证据：该格 `reference_filter.certified_continuation_steps=18`（PD 侧），即参考滤镜介入过；报告已标"类别级对照"。
- 建议：引用该格时保留"fb=18、类别级"限定；a35 三格与 b25_00_14 是 fb=0，可直接引。

### P8（低，§17 严格性）W1/W1b 产物 stamp 无 `library_sha`
- 证据：`ws1_menagerie/video/*_runtime_stamp.json`、`pads_variant/video/*_runtime_stamp.json`、`out/runs/*.json` 的 stamp 键集无 `library_sha`（有 model_sha/scene_sha256/scene_generator_sha 等）。
- 影响：该线不使用外部位姿库/权重，空缺无实质风险；但按 §17 字面"缺任一项不得进入引用链"。
- 建议：主报告引用 W1/W1b 时把"无 library_sha（该线无外部库）"备注一句。

### P9（提示，非缺陷）视频像素级复核与渲染环境的外部依赖
- `video_phys/` 未留 PNG/关键帧中间件（仅 `video_pd/frames_*` 有 745/746 张），节点无 ffmpeg/ffprobe ⇒ video_phys 的视频内容只做到"sidecar↔源 result.json↔帧数"三级一致（3/3 MATCH），未做像素级。
- 渲染 osmesa 依赖 `/data/group4/20261008-220500-codex-6c40bf04/lib/libOSMesa.so → /home/group4/.../render_test/mesa_probe/...`（他 lane 的软链，当前存在但不在本任务树内）⇒ 若该目录被清理，本任务视频无法原地重渲。
- 建议：主报告如把视频当证据，附上 sidecar 路径与 sha；重渲配方若要长期可复现，把 osmesa 软链复制进本任务树（不由本次审计执行）。

---

## 2. 总体判定

**PASS（8/8 审计项通过；0 项 FAIL）**。所有被审计的核心数字——W4a 5 格 success=2 与 S1000 同格一致（fb=0 格逐位同）、W4b 12 格 0 成功/2 个基线成功格退化为 CLOSE 超时、W4b2 9 格 3 成功与 b25 3 升 3 降/35mm 3 格对照、W4c 27 臂 25mm 2/6→3/6 与 20mm 抓住 0/4→3/4（strict 仍 0/4）与 slip 降幅、4 组 bitwise 冒烟、5 段视频的格名对应、W2 七中位数——**均从原始产物独立重算复现，未发现夸大或构造成分**。发现的 9 条问题全部是"口径/留痕/表述"级，无一条推翻结论：

- 必须在下游带限定引用的：**20mm "3/4" 是 legacy 抓握而非 success（P3）**、"W4b 恶化 12"的基线来源（P4）、b25_02_06 的 fb=18（P7）、W4c 生效 dt=0.0005（P1）。
- 可直接引用的：W4a 5 格基线（含与 S1000 的逐位同）、W4b 0/12 与 12 格 fail 分布、W4b2 3/9 与逐格升降、W4c 25mm 2/6→3/6 与全部 slip/接触指标、W2 §5 表、各视频与格的对应关系。

审计者自证（§5A.2）：以上每条数字都对应我实读的文件路径与字段值（见 §0 表内"证据路径"列），重算脚本与 stdout 落于 `ws6_review/rv_scratch/`，可重跑复核。
