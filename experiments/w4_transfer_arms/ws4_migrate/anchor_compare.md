# anchor_compare.md — 锚点单格对拍：ws4 自有副本 vs 源 rep_fixE

- 锚点格：`e35n_00_06`（源 `fixE_tally.csv` 第 23 行 `e35n_00_06,True,,104.3,3.7,0,`；T1 success 格）
- 作业参数（源 `jobs_e35n_all.txt` 第 7 行）：`e35n_00_06|35|0.266000|-0.127600|0|new_motion_cube_a_s42`
- 我方运行：`2026-10-08T14:20:26Z → 14:23:08Z`，host=worker00039，cpus=70,71，nice=19，ulimit_v=16GiB，
  **rc=0，wall_s=162**（源：`cpus=24,25`，**rc=0，wall_s=137**）
- 我方结果：`/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base/rep/out/e35n_00_06/result.json`
- 源结果（只读）：`/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/rep/out/e35n_00_06/result.json`
- runtime 版本（两侧 runtime_stamp.library_versions 相同）：`mujoco 3.2.7, numpy 1.26.4, onnxruntime 1.23.2`

## A. 关键字段（用户要求的 lift / slip / 各门 / peak_external_force）

| 字段 | 我方（副本跑） | 源 fixE | 判定 |
|---|---|---|---|
| success | True | True | **一致** |
| fail_reason | None | None | **一致** |
| hold_min_lift_m | 0.10430486125470939 | 0.10430486125470939 | **一致（逐位）** |
| tally lift_mm | 104.3 | 104.3 | **一致** |
| hold_slip_m | 0.0036965731608349936 | 0.0036965731608349936 | **一致（逐位）** |
| tally slip_mm | 3.7 | 3.7 | **一致** |
| peak_external_force | 0.0 | 0.0 | **一致** |
| final_table_min_force_last100ms_N | 0.19619999999999999 | 0.19619999999999999 | **一致** |
| final_support_by_geom_N | {floor: 0.0, table_top: 0.1962} | {floor: 0.0, table_top: 0.1962} | **一致** |
| gate_definition_version | 5 | 5 | **一致** |
| legacy_success | True | True | **一致** |
| release_height_drop_definition | 同源字符串 | 同源字符串 | **一致** |

## B. 门状态（20 门，全部逐项比对）

- 门数：mine=20，src=20；**False 门数 mine=0，src=0（全绿）**
- 逐门布尔比对：**mismatches = NONE**（20/20 相同：completed, hold_7cm, two_fingers, no_support,
  clearance_4cm, slip_1cm, release_drop_6cm, final_supported, final_fingers_off, no_external,
  no_warnings, upright, no_table_rest_in_hold, no_nonfoot_floor_support_in_hold, feet_supported_in_hold,
  fingertip_only_robot_contacts_in_hold, final_table_supported, actual_arm_speed_within_limit,
  actual_body_limits_within_2mrad, no_robot_table_contact_full_task）

## C. result.json 全叶子递归 diff（共 59 处）

| 类别 | 处数 | 说明 |
|---|---|---|
| `execution_cycle_latency/*`（各相位 median/p95/p99/max_ms） | 50 | **墙钟量**，本机满载（load 82）故偏大，例：APPROACH/median_ms 45.57 vs 38.31 |
| `/policy_median_ms`, `/policy_p95_ms`, `/model_load_s`, `/wall_s`, `/post_clearance_native_branch/branch_search_wall_s` | 5 | 同为墙钟量 |
| `/scene`, `/source/source_npz` | 3+1 | 路径字符串（含各自沙盒路径），**预期不同** |

**除墙钟量与路径字符串外，result.json 无任何物理/判定字段差异。**

## D. trajectory.npz 数值确定性（最强证据）

sha256 不同（`f82baee0…` vs `8f87a883…`，因内嵌 scene/runtime_stamp 字符串），但数组逐位比对：

| array | shape | max_abs_diff | bitwise_equal |
|---|---|---|---|
| qpos | (1593, 57) | 0.000e+00 | **True** |
| qvel | (1593, 55) | 0.000e+00 | **True** |
| body_reference | (1593, 29) | 0.000e+00 | **True** |
| hand_reference | (1593, 7) | 0.000e+00 | **True** |
| wrist_target | (1593, 3) | 0（有限项） | **True（NaN 掩码相同，去掉 NaN 后 equal_nan=True）** |
| decoded_motor_target | (1593, 29) | 0.000e+00 | **True** |
| raw_decoded_motor_target | (1593, 29) | 0.000e+00 | **True** |
| applied_motor_target | (1593, 29) | 0.000e+00 | **True** |
| actuator_ctrl | (1593, 43) | 0.000e+00 | **True** |
| phase / time / fps | (1593,) | — | **True** |
| scene / runtime_stamp | scalar str | — | False（内嵌路径/来源字符串，预期） |

=> **物理与控制信号 1593 帧逐位复现**；差异只在墙钟与路径字符串。

## E. 产物大小

| 文件 | 我方 | 源 | 备注 |
|---|---|---|---|
| scene.xml | 2429 | 2429 | **sha256 相同** `8b3958f7…` |
| contact-audit.json / balance-audit.json | 22758 / 5016 | 同 | 大小相同 |
| g1_free_grasp.xml | 51135 | 51123 | 仅第 2 行 `meshdir` 绝对路径不同（558 行中 1 行差） |
| result.json | 95935 | 95904 | 差量=墙钟数字长度+路径 |
| trajectory.npz / *.csv.gz | 微差 | 微差 | 同因 |

## F. tally 行对拍（判据列）

```
源 : e35n_00_06,True,,104.3,3.7,0,
我方: e35n_00_06,True,,104.3,3.7,0,      -> ROW_IDENTICAL（逐字节相同）
```
（我方 `fixE_tally.py` 已把 BASE 指向副本，运行 `python fixE_tally.py 0` 得 `total=1 success=1`）

## G. §5A.2 目标分支到达证明

1. 启动前实测：副本 `rep/out` 条目数 = **0**，`rep/out/e35n_00_06` **不存在**（故不可能读到旧产物）。
2. 运行 rc=0，`result.json` 由本次在 `22:23` 新生成（`utc_start=14:20:26Z, utc_end=14:23:08Z`）。
3. 我方 `result.json` 的 `source.source_npz` 字段指向 **ws4_migrate 沙盒路径** → 可证明是本副本生成，非拷贝源文件。
4. 对比字段**真有值**：lift=0.10430486125470939 m、slip=0.0036965731608349936 m、20 门全绿、peak_external_force=0.0。

## H. 结论

**该 build 可被我方独立复跑**：同一 venv/mujoco，复制 + 补 3 个 `rep/out` 输入 + 改 BASE 后，单格
在 162s 内成功，且判定字段、20 个门、8 个物理数组与源逐位相同；唯一差异是墙钟量与内嵌沙盒路径。
W4 对照实验可在此副本上直接做（用第 3 节命令逐格跑，或第 6 节批量模板）。
