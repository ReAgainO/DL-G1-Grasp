# W4e_COMB — 组合臂：位置伺服 × 接触三件套 叠加对照

- 父 TASKID: 20261008-221515-qoder-03c4673f / 子代理 ws4e（未新建 claim）
- 节点: worker00039（Step 0 探针 `worker00039 2026-10-09 00:04:50`，rc=0）
- 构建: `ws4_migrate/rep_ext_comb`（= rep_base 的 `cp -a` 副本 + 两臂改动叠加；BASE 已重定向；`.flags_flat` 与 rep_base 逐字节同）
- 规则核对: AGENTS.md sha256=`9e2c073c2ad7b602…` ✓；rep_base / rep_ext_cfg / rep_ext_pd / rep_ext_phys 全程只读；未用 sudo / 裸 crontab；未驱动其它 CLI agent；单条 ssh ≤10 分钟；**并行 ≤2 格**（每格 2 核 taskset + nice19，机器实测空闲）
- 配对产物: `steps-ws4e.md`（逐条流水）

---

## 0. 一句话结论

> **两套改动可以合成到同一副本（合成纯净性有双向字节等价证明）且同时开启。叠加效应分三层：**
> **① 35mm：PD 收益完整保留并被补全——两臂基准 1/3 成功 → PD 2/3 → 组合 3/3 全绿（a35_00_15 从"从未抬起"直接翻成全绿 137.4mm/0.66mm）；**
> **② 25mm：组合在 3 个与 W4c 同格的格上与 W4c 打平（同 1/3 成功、失败签名相同、slip/举升不劣），b25_00_00 唯一翻转格保持翻转且抬得更高（143.4 vs phys 134.1）；**
> **③ 但组合不无条件 ≥ W4c 单独：b25_12_04 上组合复现 PD 单独的"两指接触超时"（组合 F vs phys 单独 T），踢飞机制取证坐实——接触三件套压不住位置伺服的快合踢飞。**
> `fixE_tally` 全列（组合 10 次运行）：**success 5；≤1 红 8；仅 2 格失败且都是 12_04 诊断格的两遍确定性复跑。**

---

## 1. 合成方法与纯净性证明

### 1.1 改动面（先清点，后合并）

两臂相对 rep_base 的代码改动面（`diff -rq` 排除 raw*/out* 数据目录）：

| 文件 | W4b2(PD) | W4c(phys) |
|---|---|---|
| `rep/finger_control.py` | 纯追加 `finger_position_torques()`（+1218B） | 未改 |
| `rep/sonic_grasp.py` | 12 处 opcode | 5 处 opcode |
| `run_fixE.sh` | 2 处 insert | 4 处（BASE/W4C_PHYS EXTRA/w4c_phys_args meta/W4C_TIMEOUT） |
| `fixE_tally.py`、`drive_phase*.sh`、`run_my.sh` | 仅 BASE 路径 sed | 仅 BASE 路径 sed |

**唯一交集**：两臂各改 `run()` 签名的同一行尾部（`branch_coverage=False):`）；其余 16 处改动互不相邻。

### 1.2 合并方式（`ws4e_merge.py`，全程序化、无手工转写）

- 两臂改动各自**现场重算**为 `rep_base→臂` 的 difflib opcodes（全表落盘 `logs/ws4e_merge.out`）；
- **route1** = PD 内容 + phys opcodes；**route2** = phys 内容 + PD opcodes；
- 每个 opcode 以"旧块精确搜索、count==1"落位，任何缺口即 exit 2 拒绝写入；
- 唯一交叠行用规范式合并：`branch_coverage=False,finger_pd=None,finger_armature=0.,substep=1,contact_margin=0.,solref=None,impratio=0.):`

实测证明：

```
phys opcodes = 5（sig / 模型载入行 / mj_step / result 插入 / argparse 插入）
pd   opcodes = 12（import / scene_and_cal sig / armature 注入 / run sig / 断言 / 调用行 /
                  FINGER_CONTROL 打印 / FINGER_MODEL 打印 / 力矩分发 / result 落盘 / argparse / options 解析）
route1 sha256 = 574bc600d7122f2b59d616c3b0ec49587cbec300bc11b138c224633c7a7c18c3
route2 sha256 = 574bc600d7122f2b59d616c3b0ec49587cbec300bc11b138c224633c7a7c18c3
ROUTES BYTE-IDENTICAL -> 合成 = base + pd 全部 + phys 全部，无第三处差异
py-compile OK；finger_control.py comb sha 1273d587… == pd 臂 sha（纯追加复制）
run_fixE.sh comb sha = 2b2cc5ab…；bash -n OK
containment diffs（logs/ws4e_merge_*.diff）: sg_pd_comb 5 hunks（=phys 全部特性复现）、
  run_pd_comb 3 hunks（=phys 的 EXTRA/meta/timeout + BASE）、sg_phys_comb 10 hunks（=pd 全部特性）
```
人工复核每一条 hunk 均一一对应 [§1.1] 清点过的改动——无新增差异。
交叉旁证：组合副本每次运行的 `telemetry.runtime_stamp.scene_generator_sha = 574bc600…`（即组合版 sonic_grasp.py 的 sha），运行期内自证用的是合成文件。

### 1.3 运行级旁路冒烟（两开关全关 = 与 W4a 基线逐位同）

`b25_12_04__comb`（无任何 env）vs `rep_base/rep/out/b25_12_04`（W4a 基线）：
qpos/qvel/body_reference/hand_reference/wrist_target/decoded_motor_target/raw_decoded_motor_target/applied_motor_target/actuator_ctrl/time **全部 bitwise=True, max|d|=0**；success/lift/slip/duration 逐位同；gates identical；`scene.xml` sha e9b180d3… 双方逐字节同。stdout 证据：`FINGER_CONTROL mode=torque-bypass kp=0 kd=0 armature=0`、`FINGER_MODEL [0.01×7]`（模型原值）、W4C_PHYSICS 行 0 条。
⇒ **两开关"可同时关"（零扰动）与"可同时开"（§2）都成立。**

## 2. 冒烟(b)(c)：双开关开启的双证与墙钟

格 `b25_02_06__comb`，env：`FINGER_PD=100,10 FINGER_ARMATURE=0.1 W4C_PHYS="--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10"`。

- stdout（→ `raw/<N>.stdout.log`）：
  `FINGER_CONTROL mode=position kp=100.0 kd=10.0 armature=0.1`
  `FINGER_MODEL right_hand_armature= [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]`
  `W4C_PHYSICS {"requested":{"substep":4,"contact_margin_m":0.001,"solref":[0.02,1.0],"impratio":10.0},"physics_timestep_s":0.0005,"physics_hz":2000.0,"model_impratio":10.0,"geom_margin_m":[0.001×4],"geom_solref":[[0.02,1.0]×4],…}`
- 落盘证（result.json）：`finger_control{mode:position,kp:100,kd:10,armature:0.1,mean_abs_track_err_rad:0.00104,ctrl_saturation_fraction:0.17%}` + `physics_recipe_w4c{physics_timestep_s:0.0005,model_impratio:10.0,…}`；meta `sonic_grasp_args` 同时含 4 个 phys 参数与 `--finger-pd/--finger-armature`，`w4c_phys_args=` 行在。
- 墙钟：**165s**（同格 W4a 基线 183s、W4c phys 146s 档；组合全批 133–170s，≤1.1× phys 臂）。

## 3. 实验矩阵与执行

- 25mm 4 格（与 W4c 同格优先）：`b25_02_06 / b25_00_10 / b25_00_14 / b25_00_00`（00_00 = W4c 唯一翻转格；00_14 = W4b2 格）
- 35mm 3 格（与 W4b2 同格）：`a35_00_06 / a35_00_10 / a35_00_15`
- 附加诊断 2 遍：`b25_12_04__comb2/3`（双开；PD 单独在此格回归、phys 单独保住成功——直接检验"是否无冲突"）
- 全部组合臂 = 双开关同时开；driver `ws4e_drive.sh` ≤2 槽、每格 2 核 auto-pick 空核；实测各格 rc=0、墙钟 165/165/165/168/170/168/165 + 133/137s；`comb2 vs comb3` trajectory 全部 bitwise equal（确定性）。
  命令模板：`W4C_TIMEOUT=2400 FINGER_PD=100,10 FINGER_ARMATURE=0.1 W4C_PHYS="--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10" bash run_fixE.sh <name> <edge> <cx> <cy> 0 - <cpus>`

## 4. 三方对照表（同格；base=W4a 本地基线 / S1000 记录转引）

| 格(edge) | base | W4b2 PD | W4c phys | **W4e 组合** |
|---|---|---|---|---|
| b25_02_06 (25) | F 121.5/3.69 1红[table] | T 131.7/2.25 | F 129.9/0.97 1红[final_table_supported] | **F 134.4/0.63 1红[final_table_supported]** |
| b25_00_10 (25) | F 超时 13红 | F 134.9/3.53 1红[table] | F 138.2/0.88 1红[table] | **F 133.5/0.52 1红[table]** |
| b25_00_14 (25) | F(S1000) -0.1/38.04 4红 | F 131.8/3.06 1红[table] | （未跑） | **F 139.4/0.55 1红[table]** |
| b25_00_00 (25) | F 133.0/3.62 1红[table] | F -0.1/19.51 7红 | **T 134.1/0.62** | **T 143.4/0.69** |
| a35_00_06 (35) | T(S1000) 128.7/3.80 | T 122.1/2.76 | （未跑） | **T 144.1/0.67** |
| a35_00_10 (35) | F(S1000) 129.4/3.83 1红 | T 128.9/2.91 | （未跑） | **T 135.4/0.57** |
| a35_00_15 (35) | F(S1000) -0.1/20.55 3红 | F 134.1/2.76 1红[table] | （未跑） | **T 137.4/0.66** |
| b25_12_04 (25) ⚠诊断 | T 121.3/4.24 | **F 两指超时** | T 142.2/0.51 | **F 两指超时（comb2/comb3 两遍逐位同）** |

（base 列中 25mm 四格除 00_14 外为 rep_base 本地复跑；00_14 与 35mm 三格基线为 S1000 记录，经 W4b2_PD.md §3 转引。2 位小数=slip mm，3 位=lift mm。）

**fixE_tally（rep_ext_comb, CUT=1791475500）**
```
total=10 success=5
  SUCCESS: a35_00_06 144.1/0.67; a35_00_10 135.4/0.57; a35_00_15 137.4/0.66; b25_00_00 143.4/0.69; b25_12_04__comb 121.3/4.24(off 冒烟)
  near (1红): b25_00_10 133.5/0.52[table]; b25_00_14 139.4/0.55[table]; b25_02_06 134.4/0.63[final_table_supported]
  other: b25_12_04__comb2 / __comb3 = two-finger contact timeout（两遍逐位同）
```

## 5. 判据回答

**① 组合是否保持 35mm 的 PD 收益？——是，且超出。**
PD 单独 2/3 成功（a35_00_15 剩 1 红[table]）→ 组合 3/3 全绿；三格 lift 135–144mm（PD 122–134）、slip 0.57–0.67（PD 2.76–2.91）。PD 做不到的 a35_00_15"从未抬起→全绿"由组合完成。**限制**：phys 臂未跑 35mm，无法分离"这一格的翻正归因于谁"，只能说组合 ≥ 两个单独臂的并集表现。

**② 组合在 25mm 是否 ≥ W4c 单独（无冲突）？——否，有一个明确的例外。**
- 3 个 W4c 同格：成功数打平（各 1/3，都是 00_00）、失败签名一致（02_06 同为 final_table_supported、00_10 同为真·臂-桌接触单红）；组合的 slip 更低（0.52–0.69 vs 0.88–0.97）、00_00 抬升更高（143.4 vs 134.1）。
- **但 b25_12_04 例外成立**：phys 单独保住成功（T 142.2/0.51），组合复现 PD 单独的"CLOSE 两指超时"（F，两遍 comb2/comb3 逐位相同）。踢飞取证（telemetry，`logs/ws4e_kick.out`）：组合与 PD 单独均出现"合指把方块楔起"签名（comb2 在 t≈45s 方块 z +6.1mm、水平位移 16mm，随后接触崩、50.5s 超时），而 phys 单独同刻 z≈0.9mm 无位移、46.95s 建立两指接触并抬到 142mm。⇒ **PD 的"快合踢飞"是位置通道自身的失效模式，接触三件套（margin/solref/impratio/子步）不能压制它。**
- 结论口径：叠加**不新增**失败通道、不劣化既有通道，但会把 PD 的 12_04 类超时失败带进 25mm；25mm 上组合 ≈ phys − {踢飞格}。

**③ slip / 抬升数字（组合 vs 两臂）**
- slip：组合全 7 格 **0.52–0.69mm**（base 3.6–4.2；W4c phys 0.5–1.4）⇒ 接触三件套的 slip 收益在叠加后完整保留（PD 单独只有 2.25–3.53，且伴随踢飞）。
- 抬升：组合 133.5–144.1mm（base 121–133；phys 129.9–142.2），除 00_10 外均为三方最高；三格 35mm 全部 ≥135。
- HOLD 内两指接触：组合全部 **980/980 拍**（=phys 口径；base 曾出现 0/980、664/980 等）；ΣF_min（HOLD 三指合力最小值）组合 0.90–4.25N vs phys 0.89–2.00N ⇒ 组合握力下限普遍更高；pad 准静态渗透 0.21–1.42mm vs phys 0.33–0.88（个别格更深，属位置通道更硬的预期副作用，非失败征候）。

## 6. 机制观测（如实，不夸大）

1. 组合把"位置伺服的保持质量"与"接触三件套的连续性"叠加后：失败全部收敛为**两类单红**——真·臂-桌接触（00_10/00_14）或 final_table_supported（02_06），与 W4c phys 的残留红同源；25mm 残红不是数值问题而是手臂-桌子接触与收尾支撑问题（与 W4b2/W4c 结论一致）。
2. 组合的 hold 阶段跟踪质量：mean |track err| 1.04e-3 rad、力矩饱和时间占比 0.17%（单格实测；PD 单独 0.09%/0.15%）——位置通道在叠加后仍为瞬态饱和，不是全程饱和。
3. 12_04 的"组合仍超时"与 00_00 的"组合救活 PD 的踢飞"并存：同为 25mm 却结局相反，说明踢飞是否发生与方块在指间的起始相位/楔入角有关（本实验未逐格解剖，留作下一臂）。
4. 20mm 层未测（W4c 的 c20f_06_19 反向格提示 1mm margin 在 20mm 上可能有害；组合是否放大此副作用未知）——**不得外推**。

## 7. 推荐配置判断（供父会话）

- **技术可行性**：两改动可干净共存（§1 双向字节等价 + §1.3 旁路逐位 + §2 双证），一键双开：`FINGER_PD=100,10 FINGER_ARMATURE=0.1 W4C_PHYS="--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10"`；两开关全关与 W4a 基线逐位同。
- **若目标是 35mm 层或"抬升/保持质量优先"**：**组合为当前最优配置**（35mm 3/3、slip<0.7、lift 最高、HOLD 两指 980/980）。
- **若目标是 25mm 全层稳健**：**仍推荐 phys 三件套单独**（或下一步把 kp 降到 30–50/加闭合限速后再叠加）——因为组合会在"快合踢飞"格（12_04 类）损失 phys 单独能保住的成功；组合不是 25mm 的无条件替代。
- 组合与 phys 的差异集中在位置通道的 CLOSE 瞬态；**把 kp/闭合速率与接触配方解耦**是下一臂最直接的候选。

## 8. 产物与复现

- 构建: `ws4_migrate/rep_ext_comb`（sonic_grasp.py 574bc600…；finger_control.py 1273d587…；run_fixE.sh 2b2cc5ab…；`.flags_flat` 31d3d775… 逐字节同 rep_base）
- 合并脚本与证明: `ws4e_merge.py`、`ws4e_setup.sh`、`logs/ws4e_merge.out`、`logs/ws4e_merge_*.diff`（6 份 containment diff）
- 运行: `rep_ext_comb/rep/out/{a35_00_06,a35_00_10,a35_00_15,b25_02_06,b25_00_10,b25_00_14,b25_00_00}__comb/`、`b25_12_04__comb`（off 冒烟）、`b25_12_04__comb2/comb3`（诊断）；`raw/<N>.meta.txt`（含 `w4c_phys_args=` 与双参数），`fixE_tally.csv`
- 驱动/工具: `ws4e_drive.sh`、`ws4e_jobs.txt`、`ws4e_agg.py`（三方表→`logs/ws4e_agg.out`）、`ws4e_kick.py`（踢飞取证→`logs/ws4e_kick.out`）、`ws4c_metrics.py`（接触代理→`logs/ws4e_metrics.out`）、`ws4c_cmp.py`（逐位）
- 视频: `video_comb/`（组合成功格双面板 mp4 + sidecar json；记录态回放，非重积分）
  - `a35_00_15__comb.mp4`（1515 帧@25Hz，stride 4，6.25fps，137.4/0.66）sha256 `42b4fe5014ed05768213589977ccad39cae9a1753a26bcf175cfc5a9f8dea70b`
  - `b25_00_00__comb.mp4`（1501 帧，143.4/0.69）sha256 `eea28c149b818c2c4698bc44f4c78da889537ec4eb4e2604e4369b2c6c9981a4`
- 单格复跑: `cd rep_ext_comb && FINGER_PD=100,10 FINGER_ARMATURE=0.1 W4C_PHYS="--substep 4 --contact-margin 0.001 --solref 0.02 1 --impratio 10" W4C_TIMEOUT=2400 bash run_fixE.sh <cell>__comb <edge> <cx> <cy> 0 - <cpus>`

## 9. 限制

1. n 小（7 格矩阵 + 2 遍诊断）；25mm 组合未覆盖 04_01/12_04(class) 全套，04_01 未跑组合。
2. phys 臂未跑 35mm、组合未跑 20mm；跨层不可外推。
3. 无真值：slip/抬升"变好"只说明保真度，不证明"更真"。
4. base 列 35mm/00_14 为 S1000 记录转引（非本副本实跑），类别级对照。
