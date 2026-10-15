# FINDING.md — WS2: G1 Dex3-1 真机抓取数据 → 成功抓取构型先验

- TASKID: 20261008-221515-qoder-03c4673f (ws2)
- 节点: worker00039 | 沙盒: /data/group4/20261008-221515-qoder-03c4673f/ws2_dataset/
- 完成时间: 2026-10-08 22:30 (worker 本地)
- 结论: **能**。81 个成功示范 episode（0-80）全部检出抓取保持段，闭合构型统计与关节映射已产出；
  少数槽位的指别（middle/index 内部顺序）标注"待核"，不影响"闭爪目标"角值的使用。

## 1. 数据来源

- 页面: https://www.modelscope.cn/datasets/mncai/G1_Dex3_Trash_LocoManipulation
- 元数据 API: `GET /api/v1/datasets/mncai/G1_Dex3_Trash_LocoManipulation` (HTTP 200, RequestId c0bdb432-1000-4701-9252-3b4c59be3018)
- git: `https://www.modelscope.cn/datasets/mncai/G1_Dex3_Trash_LocoManipulation.git`, master = `9c28093400cb8469aa069c7a4356cdd5d22395d1`
- 单文件下载端点（实测可用，LFS 生效）:
  `GET /api/v1/datasets/mncai/G1_Dex3_Trash_LocoManipulation/repo?Revision=master&FilePath=<path>`
- 数据集自述: 118 episodes / 183,000 frames / 50 Hz / 约 61 min；`robot_type=unitree_g1_dex3`；LeRobot **v2.1**；
  0–80 正常示范，81–117 故意失败+恢复；License apache-2.0。

## 2. 体积与下载清单（实测）

| 部分 | 数量 | 体积 | 是否下载 |
|---|---|---|---|
| data/chunk-000/episode_%06d.parquet | 118 | 233,221,326 B (233.22 MB；LFS 指针求和与磁盘实测一致) | 是 |
| videos/chunk-000/observation.images.ego_view/episode_%06d.mp4 | 118 | 单集样例 18.6 MB ⇒ 估约 2.2 GB | 否（对构型提取无用） |
| meta/{info.json,episodes.jsonl,tasks.jsonl,modality.json} | 4 | 51 KB | 是 |
| assets/normal.gif 等 | – | – | 否 |

- 整包若含 videos 约 2.4+ GB；本任务仅拉 parquet+meta，实际落盘 raw/ = 223 MiB (du)。
- 下载结果: `download.log` 记 118 条 `DL episode_*.parquet http_size_time=[200 ...] actual_size=...`，
  **ok=118 fail=0**（DONE 22:21:14，约 65 秒，单文件 0.39–0.63 s）。
- sha256 对账（对着 git LFS 指针 oid）: **VERIFY_OK=118 / VERIFY_BAD=0**（`sha256_verify.txt`）。
  样例 episode_000000.parquet: size=1,972,434，sha256=`b07b4001 059e2eee...eb58cc5`（全清单在 `scripts/ws2_parquet_manifest.txt`，每行 `episode <sha256> <size>`）。
- meta sha256（`logs/meta_sha256.txt`）:
  info.json cf314630…350e / episodes.jsonl 681ffce0…80c6 / tasks.jsonl 4fa2af5a…5a6f / modality.json 45ff0cd3…da5b

## 3. 结构（解析口径）

- `meta/info.json`: fps=50, total_episodes=118, total_frames=183000, chunks_size=1000, codebase_version=v2.1。
- 43 维 `observation.state`（float64, list&lt;double&gt;）切片（与 `meta/modality.json` 完全一致）:
  `0:6 左腿 / 6:12 右腿 / 12:15 腰 / 15:22 左臂 / 22:29 左手 / 29:36 右臂 / 36:43 右手`。
- 每 episode parquet 含 31 列，除 state 外还有 `action.motion_token(64)`、`action.wbc(43)`、
  `teleop.left_hand_joints(7)`、`teleop.right_hand_joints(7)`、`observation.eef_state(14)` 等。
- `meta/episodes.jsonl` 每行附 **phase_boundaries_s = [walk→pickup, pickup→turn, turn→carry, carry→drop]**（秒），
  episode 0 长度 1616 帧 = 32.32 s，pb=[5.0, 13.98, 16.46, 23.7]。
- action 可解性: `action.motion_token(64)` 是 GEAR-SONIC v1.1 潜变量，需 `sonic_v1_1/model_decoder.onnx`
  （README 明示，sonic_release/low_latency 不可解；本任务未解，构型提取不依赖它）。
  `action.wbc(43)` 是普通关节目标、`teleop.left_hand_joints(7)` 是普通手指令，均可直接用（本任务以 observation.state 实测角为准）。

## 4. 抓取段检测（口径定义，脚本 scripts/extract.py）

对每 episode（左手 H = state[:,22:29]，O = 张开参考）:

1. `O` = H 在 [pb0−2 s, pb0]（行走末段）上的逐关节中位数（实测 ‖O‖ ≤ 0.08 rad，手确实张开）；
2. 张开度 `d(t) = ‖H(t) − O‖`；`d_hi` = [pb0, pb3] 区间 d 的 95 分位；闭合阈值 = 0.8·d_hi（实测 d_hi≈2.4–2.7）；
3. 取 **持续 ≥2 s 的最长连续闭合段** 为抓取保持段（hold）；实测 78/81 episode 只有 1 段，15/24/71 各有 2 段（取最长，另段疑似中途松开/换手位，影响可忽略）；
4. `close_onset` = hold 前最后一个 d < 0.15·d_hi 的帧；`close_complete` = hold 内首个 d ≥ 0.9·median(d_hold) 的帧；
   闭合时长 = (complete − onset)/50 s；
5. 构型三版本: `cfg_complete`（闭合完成时刻单帧）/ `cfg_hold_med`（保持段逐关节中位）/ `cfg_hold_final`（保持段最后 2 s 中位，即稳定值）。
6. **排除 81–117**（README：故意失败+恢复；按文件名 episode_000081–000117）。这 37 集同样检出保持段（=恢复后的成功抓取），
   但在 CSV 中 `excluded=1`，不参与先验统计（成功集 = episode 0–80，n=81）。

检测质量核验（logs/extract_full.out）:
- 81/81 成功集 `status=OK`；全部闭合 **onset 都在 pickup 相位内**（onset−pb0 = +1.14 ~ +11.92 s），
  且闭合完成早于 pickup 相位结束 0.96–5.56 s（均值≈3.3 s）。
- hold 时长: min 12.58 / 中位 18.12 / max 22.8 s（含抬升+转身+搬运全程握持）。

## 5. 构型统计表（成功集 episode 0–80, n=81, 单位 rad）

**稳定握持构型（推荐作为"闭爪目标"先验）cfg_hold_final（保持段最后 2 s 中位）:**

| 槽位 | 实证关节名 | min | p25 | **median** | p75 | max |
|---|---|---|---|---|---|---|
| state[22] | middle_0 (待核 m/i) | −0.9991 | −0.9839 | **−0.9738** | −0.9508 | −0.8077 |
| state[23] | middle_1 (待核 m/i) | −1.5097 | −1.4926 | **−1.4879** | −1.4711 | −1.4345 |
| state[24] | index_0 (待核 m/i) | −0.9995 | −0.9782 | **−0.9594** | −0.9245 | −0.8485 |
| state[25] | index_1 (待核 m/i) | −1.4942 | −1.4878 | **−1.4810** | −1.4604 | −1.4033 |
| state[26] | thumb_0 | −0.0135 | +0.0112 | **+0.0151** | +0.0231 | +0.0456 |
| state[27] | thumb_1 | +0.3690 | +0.5981 | **+0.6207** | +0.6544 | +0.6893 |
| state[28] | thumb_2 | +0.6025 | +0.6635 | **+0.6749** | +0.6775 | +0.6916 |

**闭合完成时刻构型 cfg_complete（同一统计口径）:**

| 槽位 | median | min | max | 备注 |
|---|---|---|---|---|
| middle_0 | −0.8799 | −0.9454 | −0.4490 | 近端关节在保持期继续"蠕变"加深 ~0.09 rad |
| middle_1 | −1.3086 | −1.4382 | −1.2034 | 远端到位快，蠕变小 |
| index_0 | −0.8885 | −0.9921 | −0.7963 | |
| index_1 | −1.3124 | −1.4704 | −1.1925 | |
| thumb_0 | +0.0133 | −0.0192 | +0.0457 | 全数据集近乎不参与抓取 |
| thumb_1 | +0.5862 | +0.3687 | +0.6539 | |
| thumb_2 | +0.6469 | +0.5712 | +0.6770 | |

差异说明: 闭合完成后再有 0.05–0.09 rad 的缓慢加深（肌腱/PD 蠕变），故建议以 `cfg_hold_med`/`cfg_hold_final` 为目标、
用 `cfg_complete` 作下限参考；若做"闭爪目标"直接下发 hold_final 中位值即可（越过限位裕度仍充足）。

**时间量:** 闭合过程时长 = **中位 0.44 s**（p25 0.42 / p75 0.46 / min 0.32 / max 0.94 s）——极快的合拢动作（≈22 帧@50Hz）。

## 6. 关节映射: 数据集关节序 → sonic-bridge 关节序

sonic-bridge 资产（只读）: `/home/group4/group4_dasc7606c/repos/sonic-bridge/g1/g1_29dof_with_hand.xml`
（29 身体 + 14 手 = 43 actuators；手 7 关节/只，命名 `left_hand_{thumb,middle,index}_{0/1/2}_joint`）；
限位：左手 middle_0/index_0 [−1.8326, 0.192]，middle_1/index_1 [−2.0944, 0]，thumb_0 [−1.0472, 1.0472]，
thumb_1 [−0.7243, 1.0472]，thumb_2 [0, 2.0944]；右手为镜像（**right_hand_thumb_2 = [−2.0944, 0]**，即线索所指）。

**映射表（左手；右手同构，值取镜像符号）:**

| 数据集槽位 | 数据集实测角（抓取中位） | → 实证关节名 | → sonic-bridge actuator 序号 (1-based / 0-based) | 置信度 |
|---|---|---|---|---|
| state[22] | −0.974 | middle_0 或 index_0（**待核**） | #33 或 #35 / 32 或 34 | 指别待核；"近端指"确定 |
| state[23] | −1.488 | middle_1 或 index_1（**待核**） | #34 或 #36 / 33 或 35 | 指别待核；"远端指"确定 |
| state[24] | −0.959 | index_0 或 middle_0（**待核**） | #35 或 #33 / 34 或 32 | 同上，与 state[22] 互补 |
| state[25] | −1.481 | index_1 或 middle_1（**待核**） | #36 或 #34 / 35 或 33 | 同上 |
| state[26] | +0.015 | left_hand_thumb_0 | #30 / 29 | 高 |
| state[27] | +0.621 | left_hand_thumb_1 | #31 / 30 | 高 |
| state[28] | +0.675 | left_hand_thumb_2 | #32 / 31 | 高（见证据 3） |

**证据链（scripts/mapping_check.py，logs/mapping_check.out）:**
1. **命令-状态配对**（81 集、|cmd|>0.05 有效帧上计算 median|cmd_j − state_k| 并求最优双射）:
   最优双射 cmd→state = [4,5,6,0,1,2,3]，配对残差 0.000/0.026–0.093 rad（次优配对 0.46+ rad），
   证明 state 块顺序是 cmd 块的 3 位轮换；结合 README 声明的手关节为 thumb 0/1/2、middle 0/1、index 0/1 →
   **state[22:29] = [middle_0, middle_1, index_0, index_1, thumb_0, thumb_1, thumb_2]**。
   （c1/c2、c3/c5、c4/c6 命令值逐帧相同，故 {拇指1,拇指2}/{两个近端}/{两个远端} 内部由命令无法进一步区分——见"待核"。）
2. **限位合规性**（118 集全体 state 极值 vs sonic-bridge 限位）:
   README 字面顺序 [t0,t1,t2,m0,m1,i0,i1] 有 **6/7 关节大幅越限**（如 −1.57 < t0 下限 −1.047）；
   实证顺序 [m0,m1,i0,i1,t0,t1,t2] 仅 1/7 越限且幅度 ≤0.02 rad（state[28] 最低 −0.0201 vs thumb_2 下限 0，属标定噪声）。
   右手同检: 字面序 6/7 越限；实证序 2/7 且均为 5e-4 量级噪声。→ 实证序成立。
3. **thumb_2 定位**: state[28] 全数据极值上限 **+1.7335 > thumb_1 上限 1.0472**，只能是 thumb_2（区间 [0, 2.0944] 内）；
   排除法得 state[27]=thumb_1。state[26] 恒 ≈0（命令恒 0，该关节全程未驱动）。
4. 边界瞬态复核: episode 首尾 ~2 s 两之手都过一遍"默认握拳"姿态（左手 [−1.56,−1.75,−1.56,−1.75,0,0,+1.73]），
   恰好与右手镜像限位/左手限位全部相容，反证映射正确；该瞬态不进入任何检测窗口。

**待核事项（无法从数据唯一确定）:** middle/index 在近端对 slots {22,24}、远端对 slots {23,25} 中的 4 个槽位的具体指别
（两指限位区间完全相同，且 81 集里两个近端关节命令恒为同一值 −1.0、两个远端恒为 −1.5）。
对"闭爪目标"使用无影响（两指对称、可交换）；若下游必须区分中指/食指，建议用视频核对 1–2 个 episode 后敲定。

## 7. 供迁移实验的"闭爪目标"建议值

- 直接可用的 7 维闭爪目标（左手，rad，数据集槽位序） = 上表 cfg_hold_final 中位列:
  **[−0.974, −1.488, −0.959, −1.481, +0.015, +0.621, +0.675]**
  （若下游用 sonic-bridge 序 [t0,t1,t2,m0,m1,i0,i1] 表达: [thumb_0 +0.015, thumb_1 +0.621, thumb_2 +0.675, m0 −0.974, m1 −1.488, i0 −0.959, i1 −1.481]）
- 容差参考: 各关节 p25–p75（见第 5 节表）；middle_0 离散度最大 (std 0.036) —— 抓垃圾袋工况本身有 ±4% 的角度波动。
- 数据集自身的"成功手部指令"电平（teleop.left_hand_joints）: [0, +0.7, +0.7, −1.0, −1.5, −1.0, −1.5]（命令序），
  与实测角高度吻合（残差 0.01–0.09 rad），说明真机闭环直接跟踪该电平。

## 8. 坑与局限

1. **首尾瞬态**: 每 episode 开头/结尾 ~1–2 s 双手呈默认握拳姿态（非任务动作），训练/分析须剔除该窗口（本提取已避开）。
2. **右手**: README 称右手全程张开；实测右手拇指/指关节存在边界瞬态且 teleop.right_hand_joints 全 0（不驱动）——右手指令通道不可作为动作训练信号；右手"张开"稳态 = [m0?,m1?,i0?,i1?,t0,t1,t2] ≈ [+1.7,+1.73,+1.7,+1.73, 0, 0, −1.74]（镜像符号）。
3. **蠕变**: 闭合完成后近端关节再加深 0.05–0.09 rad（>1 s 时间尺度），含"抓取力建立"信息；做目标时优先 hold 段稳定值。
4. **3/81 集双闭合段**（15/24/71）：取最长段的简化口径，对中位统计影响可忽略（3.7%）。另有 2 集完成时刻偏浅（middle_0 cfg_complete max=−0.449），统计已用中位/分位抗离群。
5. **videos 未下载**（省 2.2 GB）：无视觉复核；构型全部来自运动学状态。若需视觉二次核验抓取时刻，再按需补拉个别 mp4。
6. **motion_token 未解码**（需 GEAR-SONIC v1.1 decoder，hf-mirror 可能有；README 明确版本绑定）——本次提取不依赖。
7. 上传步探测（第 0 步）实测通过: worker00039 / 2026-10-08 22:16:40 / exit 0。

## 9. 产物清单（绝对路径）

| 产物 | 路径 | 说明 |
|---|---|---|
| 构型 CSV | /data/group4/20261008-221515-qoder-03c4673f/ws2_dataset/grasp_configs.csv | 118 行 × 40 列（含 excluded 标记、窗口帧号、三版构型、时长） |
| 统计表 CSV | /data/group4/20261008-221515-qoder-03c4673f/ws2_dataset/grasp_summary.csv | 21 行（7 关节 × 3 版本 × min/p25/med/p75/mean/max/std） |
| 提取脚本 | /data/group4/20261008-221515-qoder-03c4673f/ws2_dataset/scripts/extract.py | 口径全在上面; `env/bin/python scripts/extract.py full` |
| 映射核验脚本 | .../ws2_dataset/scripts/mapping_check.py | 命令-状态双射 + 限位合规 |
| 下载清单(sha256+size) | .../ws2_dataset/scripts/ws2_parquet_manifest.txt | 118 行 |
| 原始数据 | .../ws2_dataset/raw/{data/chunk-000/*.parquet, meta/*} | 223 MiB |
| 证据日志 | .../ws2_dataset/{download.log, sha256_verify.txt, logs/{extract_full.out, mapping_check.out, meta_sha256.txt}} | |
| 流水记录 | /home/group4/group4_dasc7606c/logs/20261008-221515-qoder-03c4673f/steps-ws2.md | |

复现: `cd /data/group4/20261008-221515-qoder-03c4673f/ws2_dataset && env/bin/python scripts/extract.py full && env/bin/python scripts/mapping_check.py`
（venv: /data/group4/20261008-221515-qoder-03c4673f/ws2_dataset/env，pandas+pyarrow，源 pypi.tuna）
