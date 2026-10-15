
## 8. 自然姿态抓取：朝向通道根因定位与首个 20/20 自然解

### 8.1 问题

交付版（`wb_kimo_p6l1`，20/20）虽能成功抓取，但右臂在 APPROACH 相位被扭成不自然的姿态：全片段腕部测地旋转 344.7°，其中 **APPROACH 独占 193.1°（56.0%）**，耗时 22.36 s / 560 帧。诉求是在保持抓取成功的前提下，把手臂姿态改成自然抓取。

### 8.2 根因：修正被无条件覆盖

主循环 `sonic_grasp.py`：

- `:393` `goal = last_goal.copy()`（`--kinematic-servo` 生效时）
- `:396` `if native_branch_target is not None and phase=='APPROACH' and not branch_servo_active: goal = native_branch_target.copy()` ← **无条件覆盖**
- `:400` `rawref = goal + bias → refarm → reference`

因此任何写进 `last_goal` 的 5 Hz 伺服修正，在下一步都会被 `:396` 覆盖，**永远到不了参考轨迹**。

**实测反证**：`nat4` 系列在 blend = 0.25/0.5/0.75/1.0 四种取值下，`kinematic_outer_servo.updates` 从 257 升到 316、`max_reference_increment_rad` 达 0.9753 rad（≈55.9°），**但四者轨迹逐比特相同**。IK 确实解出了大修正，却被丢弃。这解释了为何此前所有朝向实验（含 `--pinch-native-orientation` 的 7 点扫描）结果都完全一致。

另有 `native_branch.py:192` 传 `R=np.eye(3)`、`weight=0.`，即原生分支本身不使用朝向目标，朝向只由平面贴合行隐式驱动。两条证据合起来说明：**APPROACH 的朝向不由 `targetR` 控制**。

### 8.3 修复（工作副本 `harness_nat2`，交付版未动）

1. 把朝向修正从"写 `last_goal`"改为**在 `:396` 之后直接改 `goal`**，从而真正进入 `rawref → refarm → reference`。
2. 拆成两个独立开关，避免"修 APPROACH"顺手破坏已验证的抓取几何：
   - `--approach-orient-blend`：仅作用 APPROACH；
   - `--approach-grasp-orient-blend`：作用 DESCEND/CLOSE/LIFT 的 `targetR`，**本轮全程为 0**，即抓取几何与交付版同源。

### 8.4 结果

`nat5` 复核确认修正已生效（0.25 的轨迹与基线明显不同，rc 与墙钟均变化；≥0.5 触及既有的 26 s 接近时钟上限而中止）。

`nat6` 精细扫描（抓取通道固定为 0）：

| blend | 帧数 | total_geo | APPROACH 跨度 | Δ | 距自然朝向 | 门禁 |
|---|---|---|---|---|---|---|
| 0.00（基线） | 1490 | 158.34° | 146.84° | — | 122.28° | 20/20 |
| 0.05 | 1487 | 160.17° | 143.70° | −3.14° | — | 20/20 |
| 0.10 | 1479 | 156.99° | 139.57° | −7.27° | 117.78° | 20/20 |
| 0.15 | 1521 | 155.88° | 129.51° | −17.33° | — | 13/20 |
| 0.20 | 1534 | 157.31° | 124.45° | −22.39° | 102.75° | 20/20 |
| 0.25 | 1574 | 151.73° | 119.21° | −27.63° | — | 14/20 |
| **0.30** | **1582** | **151.61°** | **112.21°** | **−34.63°** | **93.12°** | **20/20** |

"距自然朝向"= APPROACH 结束时腕部姿态与 Kimodo 片段自身腕部朝向 `native_R[52]` 的测地角，随 blend 单调下降（122.28 → 93.12），证明手臂确实在向自然姿态收敛。

**胜出解 `wb_nat6_n4_o03`（blend 0.30）**：门禁 20/20；`max_lift_m` 0.1373 m、`hold_min_lift_m` 0.1208 m（门限 0.07 m）；`hold_slip_m` 0.0040 m（限 0.01 m）；`hold_min_contact_bodies` = 2；`fail_reason` 为空。相对交付版：APPROACH 扭转 −34.63°（−23.6%），终点距自然朝向 −29.16°。

**注意非单调**：0.15 与 0.25 失败、0.20 与 0.30 成功。离散接触事件使该参数不可插值预测，必须逐点实测。

### 8.5 手指时序

`thumb_2` 在 SETTLE→ALIGN 全程保持 ≈ −1.99（张开），CLOSE 收拢至 −0.935，LIFT/HOLD 恒定在 −0.945，RELEASE 重新张开至 −1.927。满足"接近前张开""抓住后保持不变"。

### 8.6 交付物

- `natural_grasp_deliverable/wb_nat6_n4_o03_natural_grasp_30fps.csv` — **1898 行 × 51 列**，30 fps；root 恒定 `[0,0,0.7887]`、quat `[1,0,0,0]`；列为 `t_s, root×3, quat×4, 29 身体关节, 7 左手, 7 右手`。
- `..._30fps.json` — 导出报告。
- `natural_grasp_deliverable/render_o03/` — 帧、关键相位 PNG、`grasp.mp4`。
- `nat3_sonic_grasp.py`（补丁）、`harness_nat2/`（工作副本）、`wb_twist_metric.py` / `wb_natural_gap.py`（度量脚本）。

交付版 `harness_s1000/rep/sonic_grasp.py` 全程保持 `0e0435b66da9b9b5`，冻结归档 `delivered_frozen_20261009` 同样为 `0e0435b66da9b9b5`，`wb_kimo_p6l1` 仍 20/20，交付 CSV 仍为 `709fd544…`。

### 8.7 局限

自然度是"更接近"而非"完全一致"：blend 0.30 下终点仍与片段自然朝向差 93.12°；继续加大 blend 会撞上 26 s 接近时钟或破坏门禁。要真正贴合，需改 `native_branch.py` 的候选打分（加入手腕自然度项），属更大改动，本轮未做。
