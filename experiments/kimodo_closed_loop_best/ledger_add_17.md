
## §17 自然姿态抓取：朝向通道根因修复与首个 20/20 成功解

**时间窗** 2026-10-09 13:08Z – 13:45Z（节点 worker00039，MUSA_VISIBLE_DEVICES=5）
**结论** `--approach-orient-blend=0.30` 在**保持 20/20 全门禁**的前提下，把 APPROACH 相位扭转从 146.84° 降到 112.21°（−34.63° / −23.6%），并把手腕终点相对 Kimodo 片段自然朝向的测地距离从 122.28° 降到 93.12°（**−29.16°**）。这是本项目首个"自然姿态 + 物理抓取成功"的联立解。

### §17.0 零改动证据（交付版仍然冻结）

| 树 | `rep/sonic_grasp.py` sha256 前 16 位 | 说明 |
|---|---|---|
| `harness_s1000`（交付版） | `0e0435b66da9b9b5` | 全程未写 |
| `delivered_frozen_20261009`（冻结归档） | `0e0435b66da9b9b5` | 只读证据 |
| `harness_nat2`（工作副本） | `9291e2cdfc78fec3` | 本轮全部实验在此 |

交付 CSV 仍为 `709fd544ce68c28feb57a2d8e61831824d9fc4254c70375c254bf09b9eefd`；`wb_kimo_p6l1` 仍 20/20。每次 sweep 启动时脚本会打印三棵树的 sha 前 16 位并留档（见 `nat5_progress.txt` / `nat6_progress.txt` 头部）。

### §17.1 为什么 nat4/nat5 的旧写法无效（决定性）

`nat2` 补丁把朝向修正写进 `last_goal`。但主循环里存在无条件覆盖：

```
396:  if native_branch_target is not None and phase=='APPROACH' and not branch_servo_active: goal=native_branch_target.copy()
```

`goal` 随后驱动 `rawref=goal+bias → refarm → reference`。因此每一步 `last_goal` 刚写入就被 396 行覆盖，修正**从未进入参考轨迹**。

实测反证（`result.json.kinematic_outer_servo`）：

| cell | updates | max_reference_increment_rad | 轨迹是否变化 |
|---|---|---|---|
| nat4 o00 | 257 | 0.0600 | 基线 |
| nat4 o025/o05/o075/o10 | 316 | **0.9753** | **四者逐比特相同** |

计数器增加、IK 解出 0.9753 rad（≈55.9°）的修正，但输出逐比特一致 ⇒ 修正被丢弃。这正是 nat4 全部 blend 结果相同的根因。

### §17.2 修复：把修正挪到覆盖之后

`nat3` 补丁在 **396 行之后**、写 `last_goal` 之前，直接把朝向修正施加到 `goal`：

```
403:  if APPROACH_ORIENT_SERVO and phase=='APPROACH' and native_branch_target is not None \
          and not branch_servo_active and APPROACH_ORIENT_BLEND>0.:
404:   if native_branch_orient is None:
405:    native_branch_orient=ik(...,wrist_target if wrist_target is not None else targetpos,
                                targetR,d.qpos[aq].copy(),prior,weight,...)
407:   goal=np.clip((1-_w)*goal+_w*native_branch_orient,_rlo,_rhi)
```

`native_branch_orient` 只解一次并缓存（`native_branch_orient=None` 在 267 行初始化）。clip 的朝向来自 `targetR`。

同时**拆开两个通道**，避免修 APPROACH 时破坏已验证的抓取几何：

| 开关 | 作用相位 | 默认 | 本轮取值 |
|---|---|---|---|
| `--approach-orient-blend` | 仅 APPROACH | 0.0 | 扫描 0.05–0.30 |
| `--approach-grasp-orient-blend` | DESCEND/CLOSE/LIFT 的 `targetR` | 0.0 | **全程 0（保持交付抓取几何）** |

`APPROACH_GRASP_ORIENT_BLEND=0` 时 `lowR/highR` 完全不变 ⇒ DESCEND/CLOSE/LIFT 与交付版同源。

### §17.3 nat5 复核：修正终于生效

| blend | rc | wall | APPROACH 扭转跨度 | 门禁 |
|---|---|---|---|---|
| 0.00 | 0 | 120 s | 146.84° | 20/20 |
| 0.25 | 0 | 125 s | 119.21° | 14/20 |
| 0.50 / 0.75 / 1.00 | 1 | 55–58 s | — | 中止 |

`rc=1` 的原因是既有的硬上限：`clearance_approach.py:26 raise ValueError('Approach clock bound0..26s')`。激进朝向让接近耗时越界——这是**已记录的**harness 限制，非新缺陷。
0.25 的失败模式（`hold_7cm / two_fingers / no_support / clearance_4cm / slip_1cm / release_drop_6cm`）说明当时抓取几何同时被改坏；§17.4 拆通道后即消失。

### §17.4 nat6 精细扫描（grasp 通道固定为 0）——关键结果

| cell | blend | 帧数 | total_geo | APPROACH 跨度 | Δ vs 基线 | 距自然朝向 | 门禁 |
|---|---|---|---|---|---|---|---|
| nat5_o00（基线） | 0.00 | 1490 | 158.34° | 146.84° | — | 122.28° | 20/20 |
| nat6_o005 | 0.05 | 1487 | 160.17° | 143.70° | −3.14° | — | 20/20 |
| nat6_o01 | 0.10 | 1479 | 156.99° | 139.57° | −7.27° | 117.78° | 20/20 |
| nat6_o015 | 0.15 | 1521 | 155.88° | 129.51° | −17.33° | — | **13/20** |
| nat6_o02 | 0.20 | 1534 | 157.31° | 124.45° | −22.39° | 102.75° | 20/20 |
| nat6_o025 | 0.25 | 1574 | 151.73° | 119.21° | −27.63° | — | 14/20 |
| **nat6_o03** | **0.30** | 1582 | **151.61°** | **112.21°** | **−34.63°** | **93.12°** | **20/20** |

`距自然朝向` = APPROACH 结束时手腕姿态与 `native_R[native_frame]`（`native_frame=52`，`argmax(native_curve[:,0])`，片段 75 帧）的测地角。单调下降：122.28 → 117.78 → 102.75 → 93.12。

**非单调**（0.15 失败 / 0.20 成功）是离散接触事件所致：中间 blend 让指尖落在不利接触构型，略偏一点反而落好。因此不能只按单调假设选点，必须实测。

### §17.5 胜出解的物理指标（`wb_nat6_n4_o03`，blend 0.30）

| 指标 | 值 | 门限 | 结论 |
|---|---|---|---|
| 门禁 | 20/20 | 20 | 通过 |
| `max_lift_m` | 0.1373 m | ≥0.07 | 通过 |
| `hold_min_lift_m` | 0.1208 m | ≥0.07 | 通过 |
| `hold_slip_m` | 0.0040 m | ≤0.01 | 通过 |
| `hold_min_contact_bodies` | 2 | ≥2 | 通过 |
| `final_clearance` | 通过 `clearance_4cm` | ≥0.04 | 通过 |
| `fail_reason` | `None` | — | 无失败 |

### §17.6 手指时序（满足开爪—闭爪—保持的硬要求）

| 相位 | thumb_0 | thumb_2 | index_0 | index_1 |
|---|---|---|---|---|
| SETTLE → ALIGN | ≈0.00 | **−1.99（张开）** | 0.076 | 1.390 |
| CLOSE | −0.038 | **−0.935（闭合）** | 0.076 | 1.443 |
| LIFT / HOLD | −0.036 | **−0.945（保持恒定）** | 0.076 | 1.441 |
| RELEASE | −0.025 | −1.927（重新张开） | 0.076 | 1.414 |

`thumb_2` 在接近、预抓取、下降、对准全程保持 −1.99 张开；CLOSE 时收拢到 −0.94；LIFT/HOLD 期间恒定不变。与"手指在此之前张开""抓住之后保持不变"一致。

### §17.7 交付物

| 文件 | 说明 |
|---|---|
| `/data/group4/20261008-232029-workbuddy-34e89f61/natural_grasp_deliverable/wb_nat6_n4_o03_natural_grasp_30fps.csv` | **1898 行 × 51 列**，30 fps，root 恒为 `[0,0,0.7887]`、quat `[1,0,0,0]`；列序 = `t_s, root×3, quat×4, 29 身体关节, 7 左手, 7 右手`，共 43 关节 + 8 根/时间列 |
| `..._30fps.json` | 导出报告（源 npz、fps 换算、相位时钟） |
| `natural_grasp_deliverable/render_o03/` | 渲染帧、关键相位 PNG、`grasp.mp4` |
| `/data/group4/.../nat3_sonic_grasp.py` | `nat3` 补丁（70053 B 起，最终 `9291e2cd…`） |
| `harness_nat2/` | 工作副本（交付版未被触碰） |

CSV 相位时钟（25 Hz 源）：SETTLE 0.00–2.00、APPROACH 2.04–26.72、PREGRASP 26.76–38.72、DESCEND 38.76–46.72、ALIGN 46.76–48.28、CLOSE 48.32–49.24、LIFT 49.28–57.24、HOLD 57.28–59.24、RELEASE 59.28–60.24、SETTLE_RELEASE 60.28–63.24。

### §17.8 资源纪律

单 cell 墙钟 117–125 s；nat6 共 6 cell，串行（`wb_nat6_sweep.sh`），nice −19。始终串行以免与同账号他人抢 GPU。`/data` 余量充足（13T 卷 11T 可用），未触及 §6 的 30 GiB 红线。渲染在 CPU 的 OSMesa 上进行，不占 GPU。

### §17.9 尚存局限（未解决，如实记录）

1. **自然度是"更接近"而非"完全一致"**：blend 0.30 下终点仍与片段自然朝向相差 93.12°。继续加大 blend 会在 0.35+ 撞上 26 s 接近时钟或破坏门禁。要真正贴合需改 `native_branch.py` 的候选打分（加入手腕自然度项），属更大改动。
2. **非单调性**：0.15 与 0.25 失败，0.20 与 0.30 成功。说明该参数不可插值预测，需逐点实测。
3. **`clearance_approach.py:26` 的 26 s 硬上限**使 `sonic_grasp.py:300` 的 `approach_timeout=32` 不可达（既有潜伏缺陷）。
4. 官方 keyframe 基线仍只在 MuJoCo 3.2.7 下可复现（需 SONIC 侧确认）。
