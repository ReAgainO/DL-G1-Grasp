# A2 — 独立复制复现：ARDY 来源运动 → 官方 SONIC v1.1 身体目标 → 独立手指控制器

- 车道：A2　父会话 TASKID：`20261008-023143-qoder-d266d3a9`
- 节点：`worker00039`（`ssh S4000`），账号 `group4`（uid 1004）
- 本车道复制根（唯一可写大目录）：`/data/group4/20261008-023143-qoder-d266d3a9/A2_sonicrep`
- 属主只读源：`/data/group4/20261006-093203-codex-6385a841`
  —— **全程只读**；未调用 `run.sh` / `ardy-grasp-run-*.sh` / `reserve_cpu_trial.py` / `snapshot_sources.py`，
  未写属主 `out/`，未消耗其配额槽，未调用任何台账写者。
- 执行解释器：`/data/group4/20261004-205550-qoder-1280b420/env/bin/python`（未改动、未 pip install）
- 全部 8 集实测于 2026-10-07T18:50Z–19:04Z 完成；**测量阶段已结束，本文以下为写作阶段产物。**

---

## verdict

**能复现。** 在父会话自有目录的一份独立复制里，用属主公开的第七波成功配方（**去掉 `--motion-profile`**，
见「纠正 2」）跑一集，得到 `success = true`、HOLD 最低抬升 **125.7953698877 mm**、
与属主成功件 `out/w7_repeat327/result.json` 的差 **= 0.0000000000 mm**，`gates` 20 门全绿，
且 10 个关键字段与属主件**逐值完全相同**（含 `duration_s = 59.6240000000269`）。
负对照（同一命令 + `--no-grip`）`success = false`，6 门红，方块从未离桌（HOLD 最低抬升 −0.092 mm），
两臂方块侧读数在**第 22366 行开始真实分岔**（`cube_z_m` 最大差 0.1434 m）⇒ 对照有效。
复现件保持 `base_fixture=false / free_base_exercised=true / body_action_override=false /
peak_external_force=0.0 / fixture_constraint=null / sonic_armature=false`，mujoco 3.2.7，
`scene_generator_sha` 与 `library_sha.sonic_v11` 均与属主件同值。

- 成功集数：**5 / 8**（T1 成功臂 1 + 扩展臂 4）
- 失败集数：**3 / 8**（T1 负对照 1 属**预期失败**；扩展臂 2 属单变量探测失败）
- T1 谓词 P1/P2/P3/P4：**全部 PASS**
- 复制体积 **332.6 MiB（348,721,200 B）**，两端 sha256 逐件比对 **DIFF = 0**（888 件中 881 SAME + 7 SELF_NEW）
- 阻塞：**无**

---

## 判据（谓词）—— 在任何一集启动之前冻结，事后未改

判据只读 `result.json` 的 `success` 与 `gates`；`rc`（进程退出码）**不是**成功位，只作运行完整性记录。

- **P1 成功臂**：`result.json.success == true`，且
  `|hold_min_lift_m × 1000 − 125.7953698876788| ≤ 1.0 mm`
- **P2 负对照臂**：同一命令 + `--no-grip`，`result.json.success == false`
- **P3 两臂必须分岔**：两臂**方块侧读数**（`telemetry.csv.gz` 的 `cube_x_m/cube_y_m/cube_z_m`
  三列 + `result.json` 的 `hold_min_lift_m, hold_slip_m, max_lift_m, max_drift_m,
  final_table_min_force_last100ms_N, hold_min_contact_bodies`）不得逐字节全同；
  若全同 ⇒ 判「**对照失效（缺陷）**」，不得当成「两臂都成功」
- **P4 复现件自身完整性**（非成功位，任一不成立则复现无效）：
  `base_fixture == false`、`free_base_exercised == true`、`body_action_override == false`、
  `peak_external_force == 0.0`、`fixture_constraint == null`、`sonic_armature == false`、
  `runtime_stamp.mujoco_version == "3.2.7"`、
  `scene_generator_sha == 28512909961057ab7f9c93144f633b5f0ca7f6b5aae9c1b05d80661baa59165c`、
  `library_sha.sonic_v11 == 75815b28521b43d96c9abf6a1ac546763ac9c384eda6b8dd6389d7c15300fef2`
- **P5 扩展臂**：只允许**单变量**改动，且必须落在 `sonic_grasp.py` 的 `assert` 合法域内。
  扩展臂**不是**随机成功率，只报「该单变量点通过/不通过」。
- 放宽任何闸门 = 本车道结论作废。P1 未过时不调参过线，直接进「失败与原因」。

**P1 PASS　P2 PASS　P3 PASS　P4 PASS　P5（6 臂，每臂经 token 级 diff 核验只改 1 个变量）已执行**

---

## 一、T1 锚点核对（全部对上）

| # | 锚点 | 期望 | 实测 | 结论 |
|---|---|---|---|---|
| 1 | `sha256sum …/sonic_grasp.py` | 611 行 / 60,824 B | `28512909961057ab7f9c93144f633b5f0ca7f6b5aae9c1b05d80661baa59165c`，611 行 / 60,824 B | 一致 |
| 1 | `sha256sum …/adaptive_hand.py` | 4,139 B | `892bff4b931f9df1836d685b2cea0a233783f32cfdf8738e51cf41aeb038986f`，49 行 / 4,139 B | 一致 |
| 2 | `$PY -c "import mujoco,onnxruntime,numpy"` | `3.2.7 1.23.2 1.26.4 3.10.22` | **原样跑报 `ModuleNotFoundError: No module named 'onnxruntime'`** | 见「纠正 1」 |
| 2 | 同上，先把 `<copy_root>/pydeps` 入 `sys.path` | — | `mujoco 3.2.7 / numpy 1.26.4 / ort 1.23.2 / py 3.10.22 (Clang 22.1.3)` | 一致 |
| 3 | 成功位 | `success=true` | `success = true`、`legacy_success = true`、`fail_reason = null`、`gates` 20 门全 `true` | 一致 |
| 3 | 「HOLD 最低抬升」真实键名 | ≈125.795 mm | 键名 **`hold_min_lift_m`**（单位 **米**）= `0.1257953698876788` ⇒ **125.7953698876788 mm** | 一致 |
| 3 | `runtime_stamp.library_sha.sonic_v11` | `75815b28…0fef2` | `75815b28521b43d96c9abf6a1ac546763ac9c384eda6b8dd6389d7c15300fef2` | 一致 |
| 4 | `control-profile.json` | 1,739 B | 1,739 B，sha `81abc21545ba479745de28513519989b0c78c9e8cb10c31c4e5c0a42e2eea2f7`（由 `w7_control43_327/result.json.motion_profile.profile_sha256` 反证） | 一致 |
| 4 | `merged-source-summary.json` | 7,771 B | 7,771 B，sha `613e6e7ce10e24874bf0b25351c1c7414d6aa5e0ec056d58b4de97af834bce33`（= `control-profile.json.generation_summary_sha256`） | 一致 |

### 锚点 4：`control-profile.json` 引用的全部源文件（已一并整目录复制）

| 角色 | NPZ | CSV | NPZ sha256 |
|---|---|---|---|
| reach | `out/w7-generated-text/w7_control_s43.npz` | `out/w7-generated-text/w7_control_s43.csv` | `62607734726d37cba47ef2b0c1c1fc53d0c2cc9200e6181a1b281376b01dc5b3` |
| lift | `out/generated_phases2/lift_s42.npz` | `out/generated_phases2/lift_s42.csv` | `d9c93e72977af4853041063bccd87665f1ebb727b9c8a4c1f3003b01cb2fcdf5` |
| hold | `out/generated_phases2/hold_s42.npz` | `out/generated_phases2/hold_s42.csv` | `4fc6a571e6661b9c345f5b1e669fbcd6d7713029e99d4b4c066dc5e0ad731096` |
| release | `out/generated_phases2/release_s42.npz` | `out/generated_phases2/release_s42.csv` | `961dbba514c4ce6e3c31c30a44f7d9e98451477fe03df37fd616f1a0a2b2bc57` |

外加 `generation_summary` = `out/w7-source-binding/merged-source-summary.json`，它再引用
`out/generated_phases2/summary.json`（`a1555c93…`）、`out/w7-generated-text/summary.json`（`171c1690…`）、
`out/w7-generated-text/run.json`（`ac56d4da…`）。
⇒ `out/w7-source-binding/`、`out/generated_phases2/`、`out/w7-generated-text/` **三目录整体复制**，
`MotionProfile` 的全部 sha 断言在复制件上均可满足（本车道 T1 未启用它，见纠正 2）。

---

## 二、对父会话假设的纠正（一手路径 + 原始报错）

### 纠正 1 — `onnxruntime` 不在解释器 site-packages，而在属主项目内的 `pydeps/`

锚点 2 的命令按原样写会**失败**：

```
$ /data/group4/20261004-205550-qoder-1280b420/env/bin/python -c "import mujoco,onnxruntime,numpy,sys;..."
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'onnxruntime'
```

`…/env/lib/python3.10/site-packages` 里只有 mujoco 3.2.7 / numpy 1.26.4 / torch 2.14.1+cpu / pyyaml 等，
**没有 onnxruntime**。真实机制在 `sonic_v11.py:14-19`：

```python
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'pydeps'))
import onnxruntime as ort
import yaml
sys.path.insert(0,str(ROOT/'official_refs'))
from sonic_action_adapter import DEFAULT_ANGLES, I2M, M2I, ACTION_SCALE, KP, KD
```

⇒ **必须复制 `pydeps/`（52 MB：`onnxruntime 1.23.2` + `flatbuffers` + `yaml`）与 `official_refs/`（296 KB）**，
否则 `sonic_grasp.py` 连 import 都过不去。这也解释了为什么属主 `run.sh` 里**没有** `PYTHONPATH` 导出——
路径注入是 `sonic_v11.py` 自己按 `__file__` 做的，所以「cd 到复制根」并不是关键，
「`sonic_v11.py` 与 `pydeps/`、`official_refs/` 同处一个根」才是关键。

### 纠正 2（**最关键**）— 成功件 `w7_repeat327` **没有**用 `--motion-profile`

父会话给的配方末尾带 `--motion-profile out/w7-source-binding/control-profile.json`。一手证据表明它**不属于**成功配方：

- `/data/group4/20261006-093203-codex-6385a841/out/w7_repeat327/result.json`：
  - `"motion_profile": null`
  - `runtime_stamp.library_sha` 中 **`input_profile` 与 `generation_summary` 两个键 ABSENT**
    （`sonic_grasp.py:38` 只在 `selected_profile is not None` 时才写这两个键）
  - `runtime_stamp.library_sha.native_npz = 78eac68c405ceae93cb737b58022e83b5251d9d71def1eedb417caae0b73daff`
    = `src/original_motions/near_s42.npz`，即 `sonic_grasp.py:141` 的**默认 reach 分支**
  - `result.source.source_npz` 直接写着 `/data/group4/20261006-093203-codex-6385a841/src/original_motions/near_s42.npz`
- 真正带该 profile 的两集**都是失败的**：
  - `out/w7_control43_327/result.json` ⇒ `success=false`，红门 `no_robot_table_contact_full_task`，
    `hold_min_lift_m=0.1143338603328955`（114.334 mm），`native_npz=62607734726d…`，`input_profile=81abc215…`
  - `out/w7_control43_314/result.json` ⇒ `success=false`，同一红门，120.169 mm
- 属主报告 `reports/20261006-093203-codex-6385a841-wave7-progress1-report.md`
  §三 表格：第 2 行 `w7_repeat327|3.2.7|125.795|6.148|0.000000|True`，第 4/6 行 `w7_control43_*|…|False`；
  §六 把 `--motion-profile` 单独放在**下一行**且写「`control-profile.json` **或** `newtext-profile.json`」
  ⇒ 那是**可选变体**，不是成功配置的组成部分。
- 负对照 `out/w7_nogrip314/result.json` 同样 `motion_profile=null`、`native_npz=78eac68c…`。

⇒ **T1 复现命令 = 父会话 flag 串去掉 `--motion-profile …`。**
若带着它跑，复现出来的是 114.334 mm 的**失败**臂，与 P1 的 125.795 mm 差 11.46 mm，必然判负。
`out/w7-source-binding/` 及其全部源文件**仍然照复制**（锚点 4 要求 + 留作后续变体），只是 T1 主复现不引用。
本车道实测印证：`a2rep327_1` 的 `motion_profile=null`、`input_profile=<ABSENT>`、`native_npz=78eac68c…`。

### 纠正 3 — 扩展旋钮合法域比父会话列的窄；`--table-front .22/.26` 与 `--finger-gain 4` 会直接 AssertionError

`sonic_grasp.py:582-604` 原文断言（节选）：

```
assert .23<=a.table_front<=.245            assert a.table_front==.23 or a.direct_table
assert 1<=a.finger_gain<=3                 assert .07<=a.lift_height<=.2
assert a.lift_height==.1 or a.grip_frame_lift
assert .25<=a.grip_preload_mm<=2.5         assert a.grip_preload_mm==.5 or a.adaptive_hand
assert .005<=a.capture_radius<=.025        assert .02<=a.contact_entry_dwell<=.2
assert .25<=a.close_seconds<=2             assert -.2<=a.neutral_shoulder_offset<=.4
assert 6<=a.grip_face_half_mm<=15          assert .5<=a.execution_speed_limit<=3.
assert 1<=a.arm_gain<=4                    assert 1<=a.lift_damping<=4
assert 8<=a.align_seconds<=25              assert .01<=a.postcapture_servo_cap<=.06
```

- `--table-front .22` ⇒ 越下界（0.23）；`--table-front .26` ⇒ 越上界（0.245）。两者**跑不起来**。
  `table_placement.py:place_direct_table()` 里还有一层同样的 `.23..​.245` 检查。
- `--finger-gain 4` ⇒ 越上界（3）。**跑不起来**。
- 另注：`--opponent` 的 argparse **默认是 `index`**（`choices=['index','middle']`），成功配方显式给 `middle`。
- P5 合法扩展域：`--table-front ∈ {.23, .245}`、`--finger-gain ∈ {1, 2}`、
  `--lift-height ∈ [.07,.2]`（≠.1 时必须保留 `--grip-frame-lift`）、`--grip-preload-mm ∈ [.25,2.5]`、
  `--capture-radius ∈ [.005,.025]`、`--contact-entry-dwell ∈ [.02,.2]`、`--close-seconds ∈ [.25,2]`、
  `--neutral-shoulder-offset ∈ [-.2,.4]`、`--opponent ∈ {index,middle}`、`--execution-speed-limit ∈ [.5,3]`。

### 纠正 4 — `finger_clearance` 不是 `sonic_grasp.py` 的直接 import

`sonic_grasp.py:11-33` 的直接 import 里**没有** `finger_clearance`；它经 `adaptive_hand`/`clearance_approach`
间接进闭包，同时被 `runtime_stamp` 的 sha 清单显式列出（`sonic_grasp.py:38`）。文件已复制、sha SAME。

### 纠正 5 — 输出目录由 `__file__` 决定，不由 `cd` 决定；且 `out/<name>` 已存在会直接崩

`sonic_grasp.py:129`：`root=Path(__file__).resolve().parent; out=root/'out'/name; out.mkdir()`。
⇒ 只要 `sonic_grasp.py` 在复制根里，输出必落
`/data/group4/20261008-023143-qoder-d266d3a9/A2_sonicrep/out/<name>/`，**结构上不可能**写进属主 `out/`。
`--motion-profile` 的相对路径也由同一个 `root` 解析：`motion_profile.py:MotionProfile(root, relative)` →
`bounded_path()` 做 `resolve()` + `is_relative_to(root)` + 拒绝绝对路径/`..`/错误后缀 ⇒ 越界即 `ValueError`。
`out.mkdir()` 不带 `parents=True` 且**目录已存在会抛 `FileExistsError`** ⇒ 每集必须全新名字
（`run_own.sh` 里已做前置拒绝，rc=3）。`cd` 到复制根仍照做（与属主纪律一致），但不是决定性因素。

### 纠正 6 — 复制时必须单独带上 `out/pinch-feasibility.json`

`--endpoint-seed` 会让 `runtime_stamp` 去 sha `root/'out/pinch-feasibility.json'`（`sonic_grasp.py:43`）。
该文件在属主 `out/` 的**顶层**（10,339 B），不在任何 `w7_*` 子目录里。
若按「排除 `out/` 下大 result 目录」一刀切，很容易连它一起排掉 ⇒ `FileNotFoundError`。已单独复制。
（`out/official-dynamics.json` 只有 `--sonic-armature` 才需要，成功配方不用；为完整性也复制了。）

### 纠正 7 — `--table-front` 在 `[.23,.24]` 区间内**不产生物理效果**（本车道新测出）

见「三、扩展臂」里 `a2x_tfront23_1` 一节：改成 `.23` 后，方块侧三列 telemetry 与 T1 成功臂
**逐字节相同**（29,812 行、`max_abs_diff = 0`），`result.json` 只有 10 个键不同，其中唯二的实质键是
`table_front_x_m`（0.24→0.23）与 `table_placement_adaptation`（true→false），
外加 `post_clearance_native_branch` 里 7 个候选的 `open_robot_table_clearance_m`
（如 selected：0.05555757822975883 → 0.05055757822975883），而**被选中的分支 `body_q` 逐位相同**、
`seed_label` 与 `branch_selected_time_s` 相同 ⇒ 执行物理完全一致。
这与属主自己测到的「`--finger-table-clearance-mm 1` 声明了参数但轨迹逐位未变」是同一类现象。
**因此 `--table-front` 不是一个可用的物理单变量旋钮（至少在此区间/此配置下）；把它当扩展维度会得到假阳性「通过」。**

---

## 三、清点、复制与闭包

### `du -sh` 属主目录逐项（只读观测）

```
2.7G  属主目录总计
1.2G  out/              （其中 ~1.19G 是 ~180 个历史 result 目录）
191M  sonic_v11/        model_encoder.onnx 50,117,796 B + model_decoder.onnx 149,778,638 B + observation_config.yaml 2,475 B
 89M  src/              g1/ 33M（含 meshes）、ardy_runtime/ 54M、original_motions/ 1.2M、manual_grasp_calibration.npz 424K
 52M  pydeps/           onnxruntime 49M + yaml 2.9M + flatbuffers
 49M  uv-cache/         — 排除
 17M  source-snapshots/ — 排除（属主快照器产物）
1.6M  cache/            — 排除
832K  tmp/              — 排除
296K  official_refs/    sonic_action_adapter.py / ardy_mujoco_converter.py / g1_training.py / …
8.0K  mujoco314-only/   — 排除（只切 MuJoCo 3.14 包；本车道只用 3.2.7）
1.23G 顶层 wave*.tar.gz 历史证据包 — 排除（首次 cp 误带上，已删）
```

### 实际复制内容（`cp -a`，保持相对路径结构）

- 顶层全部常规文件（173 个 `.py` + `.json` + `.sh`），**除** `*.lock` / `wave*.tar.gz` /
  `wave*-summary.json` / `wave*-progress*.json` / `wave*-launches.jsonl` / `wave*-write-probe.bin`
- `sonic_v11/`、`pydeps/`、`official_refs/`、`src/` 四个目录整体
- `out/pinch-feasibility.json`、`out/official-dynamics.json`
- `out/w7-source-binding/`、`out/generated_phases2/`、`out/w7-generated-text/` 三目录整体

**复制总体积：348,441,923 B = 332.3 MiB（`du -sb` 348,772,561 / `du -sh` 335M）
⇒ 断言 ≤ 4 GB：PASS（用了 8.1%）。**
跑完 8 集后整个 `A2_sonicrep` 为 418 MB（新增 83 MB 是 8 集的 `out/a2*` 输出），仍在 `/data`（11T 可用），
`/home` 未增加大件（仍 7.4G 可用）。

### 两端 sha256 逐件比对 → `A2_sonicrep/COPY-MANIFEST.tsv`

```
files=888  SAME=881  SELF_NEW=7  DIFF_or_UNEXPECTED=0  total_bytes=348719995 (332.6 MiB)
size_bound_4GiB=PASS     manifest_rc=0
```

- **DIFF = 0**，无需停下。7 件 `SELF_NEW` 全是本车道自写：
  `A2-CLOSURE.txt`、`A2-IMPORT-PROBE.txt`、`A2-PRUNE-LIST.txt`、`COPY-MANIFEST.tsv`、
  `FINDING.md`、`a2_metrics.py`、`run_own.sh`。
- 关键件复核：`sonic_grasp.py` `2851290996…baa59165c` SAME；`adaptive_hand.py` `892bff4b93…38986f` SAME；
  `sonic_v11/model_decoder.onnx` 149,778,638 B SAME；`model_encoder.onnx` 50,117,796 B SAME；
  `src/manual_grasp_calibration.npz` SAME；`src/g1/**` 全部 SAME；`out/pinch-feasibility.json` SAME。
- **跑完 8 集之后又重算了一次**（`raw/A2-POSTRUN-VERIFY.tsv`，跳过 `out/a2rep*`、`out/a2x*`）：
  `files=888 SAME=881 SELF_NEW=7 DIFF=0` ⇒ **8 集仿真没有改动任何一份被复制的代码/权重/资产**。

### 主动剪除（`A2_sonicrep/A2-PRUNE-LIST.txt`，含属主侧 sha256）

6 件**故意不复制**：它们硬编码属主 task id，一旦被误调用会写属主目录 / 消耗属主配额槽；
且都**不在** `sonic_grasp.py` 的 import 闭包内，剪除对复现零影响。

| 文件 | 属主侧 sha256 | 原因 |
|---|---|---|
| `run.sh` | `86db3c2e0ffea07b9965c01a03da1ee1b0aebeaa52a363fabec0269fe80af7f5` | `rules_sha` 断言 + `reserve_cpu_trial.py` 闸 + `tee` 属主 `logs/…/steps.md` |
| `run.wave7.sh` | 同上（与 `run.sh` 同内容） | 同上 |
| `ardy-server-entry.sh` | `ccb6e1c7cdb9352955a2dad5a1e17c3a033d94d82021a08a561b8c7604a8e906` | `simulate` 子命令直接 `exec bash run.sh` |
| `ardy-server-entry.wave7.sh` | 同上 | 同上 |
| `reserve_cpu_trial.py` | `00a24fbc31a3a1378a0e50ad757063156292c45ea19b5541721f2cf451605d66` | 属主私有配额闸本体 |
| `snapshot_sources.py` | `8cdbb9e2f6d8b7d8b5cb893a4b3f270f1243763c79f38bfd6ff41797b734952e` | 属主快照写者 |

其余 147 个从入口不可达的 `.py`（`checkpoint_*`、`record_progress`、`begin_wave*`、`incremental_*_git`、
`deploy_wave7_*`、`wave*_records`、`merge_wave7_progress2_issue` 等台账/记录写者）**保留在复制里但绝不调用**。

### import 闭包（`A2_sonicrep/A2-CLOSURE.txt`）

AST 递归 BFS，搜索根 = 复制根 + `official_refs/`；`pydeps/` 视为 vendored 第三方，只验在场不递归：

```
CLOSURE_LOCAL_MODULES(27) —— 全部在场，缺失 0：
  adaptive_hand balance_audit branch_execution branch_face_ik clearance_approach contact_audit
  cycle_latency decoded_arm_filter discrete_reference execution_monitor finger_clearance
  finger_control grasp_geometry motion_input motion_profile native_branch neutral_pose
  policy_reference reference_filter setdown_plan sonic_action_adapter(official_refs/) sonic_grasp
  sonic_v11 source_physics_core table_placement task_plan trajectory
EXTERNAL_TOPLEVEL(17): argparse collections csv gzip hashlib json math mujoco numpy onnxruntime
                       os pathlib subprocess sys time xml yaml
VENDORED OK: pydeps/onnxruntime/__init__.py 14,874 B | pydeps/yaml/__init__.py 12,311 B
             sonic_v11/model_encoder.onnx 50,117,796 B | model_decoder.onnx 149,778,638 B
             observation_config.yaml 2,475 B
TOPLEVEL_PY_TOTAL=173  REACHABLE=26  UNREACHABLE_FROM_ENTRY=147
```

实跑 import 探针（`A2_sonicrep/A2-IMPORT-PROBE.txt`，与 `run_own.sh` 完全相同的环境导出）：

```
cd <copy_root>; ulimit -v 16777216; timeout 300 taskset -c 0-3 $PY -B sonic_grasp.py --help
probe_rc = 0     输出 4,190 B / 106 行
grep -c "ImportError|Traceback|ModuleNotFoundError|No module named" = 0
31/31 配方相关 flag 在 --help 里全部 OK，MISS = 0
```

⇒ **零 ImportError、零缺件，未改任何一行被复制的代码。**

---

## 四、我自己的 runner（无配额闸、无 rules_sha）

`A2_sonicrep/run_own.sh`　sha256 `f4e2368f16544439f485ffd345a6de1ecfddb7ea4fc9dc78dfe70b99eedc4ccc`（3,404 B）

```
PY=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
TMPDIR=<copy_root>/tmp   XDG_CACHE_HOME=<copy_root>/cache   MUJOCO_GL=disable
unset PYOPENGL_PLATFORM ; unset DISPLAY
ulimit -v 16777216                 # 16 GiB AS
cd <copy_root>
timeout --foreground --kill-after=5s ${A2_TIMEOUT:-900} taskset -c ${A2_CPUS} nice -n 19 \
  $PY -B sonic_grasp.py <NAME> …
```

与属主 `run.sh` 的**刻意差异**（其余物理相关导出照抄）：去掉 `rules_sha`/`AGENTS.md` 断言、
去掉 `reserve_cpu_trial.py` 闸、去掉 `snapshot_sources.py`、去掉对属主 `logs/…/steps.md` 的 `tee`、
`timeout` 由 300 s 放宽到 900 s。每集把 stdout/stderr 落 `raw/<NAME>.stdout.log`，
环境/版本/CPU 集/ulimit/前后 `/proc/pressure`/`df` 落 `raw/<NAME>.meta.txt`，
`result.json` 另存一份 `raw/<NAME>.result.json`。输出名已存在时**前置拒绝**（rc=3）。

**并发纪律**：开工前 `nproc=128`、`/proc/pressure/cpu some avg10=0.00` ⇒ 按 ≤4 并发。
T1 两臂**顺序**跑（不并发），以免任何争用干扰「逐位相同」判定；CPU 集 `96,97,98,99`。
T2 批 1 以并发 3 启动（`96-99`/`100-103`/`104-107`，互不重叠，`nice -n 19`）；
启动后 47 s 复测到 `some avg10=20.31`（>10）、`loadavg 125.40` ⇒ **按纪律降级**：
用 pid 文件 + `/proc/<pid>/cmdline`(`bash …/t2_driver.sh`) + `Uid: 1004` + `cwd=<copy_root>`
三重核验后，只对驱动 pid `2339311` 发 `SIGTERM`（**未用 `pkill -f`**），
使其无法自动拉起批 2；批 1 的三个子进程被 reparent 后正常跑完（已核 `cwd`）。
批 2 改由 `t2b_driver.sh` 以**并发 2** 执行，并在日志里写明降级原因与当时的 pressure/loadavg。

---

## 五、T1 复现命令（冻结）与逐 flag 对照

成功臂 `a2rep327_1`（父会话 flag 串**去掉 `--motion-profile`**，见纠正 2）：

```bash
bash run_own.sh a2rep327_1 \
  --strict-execution --finger-gain 3 --grip-preload-mm 1.5 --table-front .24 \
  --lift-height .15 --reference-fallback --grip-frame-lift --direct-table \
  --adaptive-hand --kinematic-servo --pinch-geometry --flat-pinch --surface-capture \
  --phase-clips --capture-radius .007 --c2-reference --endpoint-seed \
  --endpoint-seed-native --contact-close --contact-entry-dwell .04 --gravity-arm 1 \
  --opponent middle --close-seconds .5 --neutral-shoulder-offset .2 \
  --clearance-approach --clearance-native-branch --clearance-branch-servo
```

负对照臂 `a2rep327_nogrip_1` = 同一命令 + `--no-grip`。

配方逐 flag ↔ 属主成功件回显字段（全部取自 `out/w7_repeat327/result.json`，非推测）：

| flag | 属主成功件回显 |
|---|---|
| `--strict-execution` | `strict_execution_gate_enabled = true` |
| `--finger-gain 3` | `independent_finger_kp_gain = 3.0`（`kd = 1.7320508…` = √3） |
| `--grip-preload-mm 1.5` | `grip_preload_mm = 1.5`，`adaptive_hand.geometric_pad_preload_m = 0.0015` |
| `--table-front .24` | `table_front_x_m = 0.24000000000000005`，`table_placement_adaptation = true` |
| `--lift-height .15` | `requested_postcapture_lift_height_m = 0.15` |
| `--reference-fallback` | `reference_filter.continue_certified_enabled = true`，`certified_continuation_steps = 42` |
| `--grip-frame-lift` | `grip_frame_lift = true` |
| `--direct-table` | `direct_table = true`，`object_support = "broad table, no pedestal"` |
| `--adaptive-hand` | `grip_preload_adaptation = true`，`adaptive_hand.calls = 110` |
| `--kinematic-servo` | `kinematic_outer_servo.enabled = true`（258 updates，5 Hz，cap 0.06 rad） |
| `--pinch-geometry` / `--flat-pinch` / `--surface-capture` | 三个同名字段全 `true` |
| `--phase-clips` | `phase_clips_loaded = true`，`phase_clips_consumed = [hold_s42, lift_s42, release_s42]` |
| `--capture-radius .007` | `preclosure_capture_radius_m = 0.007` |
| `--c2-reference` | `c2_reference = true` |
| `--endpoint-seed --endpoint-seed-native` | `endpoint_branch_loaded = true`；`endpoint_seed` sha 入 `library_sha` |
| `--contact-close` | `preclosure_contact_close_enabled = true` |
| `--contact-entry-dwell .04` | `preclosure_contact_dwell_s = 0.04` |
| `--gravity-arm 1` | `right_arm_gravity_feedforward_scale = 1.0` |
| `--opponent middle` | `opposing_pad = "right_middle_fingertip"` |
| `--close-seconds .5` | `close_command_duration_s = 0.5` |
| `--neutral-shoulder-offset .2` | `neutral_shoulder_offset_rad = 0.2` |
| `--clearance-approach` | `clearance_approach` dict（`actual_wrist_clearance_z_m = 0.9`） |
| `--clearance-native-branch` | `post_clearance_native_branch_enabled = true` |
| `--clearance-branch-servo` | `post_clearance_branch_servo_enabled = true` |
| （**无** `--motion-profile`） | `motion_profile = null`，`native_npz = 78eac68c…`（`near_s42.npz`） |
| （**无** `--no-grip`） | `no_grip = false` |
| 其余全取 argparse 默认 | `weight=.03 / align_seconds=8 / arm_gain=1 / lift_damping=1 / reference_margin=.002 / postcapture_servo_cap=.06 / execution_speed_limit=2 / grip_face_half_mm=15 / finger_table_clearance_mm=0` —— 与成功件回显逐一相符 |

属主成功件 `wall_s = 115.43`、`duration_s = 59.624`；本车道复现件 `duration_s = 59.6240000000269`（同）、
runner 墙钟 128 s（含模型加载，节点当时 loadavg 12–125）。

---

## 六、逐集数字表

`Δ` = `|hold_min_lift_m×1000 − 125.7953698876788| mm`。墙钟 = `run_own.sh` 记录的整进程墙钟（含模型加载）。
所有 8 集 `rc = 0`；`rc` **不是**成功位，成功位只取 `success` 与 `gates`。
所有 8 集 `mujoco = 3.2.7`、`scene_generator_sha = 2851290996…baa59165c`、
`library_sha.sonic_v11 = 75815b28…300fef2`、`native_npz = 78eac68c…d73daff`、
`motion_profile = null`、`input_profile = <ABSENT>`。
路径前缀统一为 `/data/group4/20261008-023143-qoder-d266d3a9/A2_sonicrep/out/`。

| 名字 | 变量（相对冻结配方，**单变量**） | success | HOLD 最低抬升 mm | Δ mm | 失败门 | 墙钟 s | `duration_s` | result.json |
|---|---|---|---|---|---|---|---|---|
| `a2rep327_1` | 无（T1 冻结配方） | **true** | **125.7953698877** | **0.0000000000** | 无（20/20 绿） | 128 | 59.6240000000269 | `…/out/a2rep327_1/result.json` |
| `a2rep327_nogrip_1` | `+ --no-grip`（**负对照**） | **false** | −0.0921214582 | 125.8874913459 | `hold_7cm` `two_fingers` `no_support` `clearance_4cm` `slip_1cm` `release_drop_6cm` | 125 | 59.250000000026446 | `…/out/a2rep327_nogrip_1/result.json` |
| `a2x_opp_index_1` | `--opponent middle → index` | **false** | −1000.0（**无 HOLD 窗**） | — | 11 门：`completed` `hold_7cm` `two_fingers` `no_support` `clearance_4cm` `slip_1cm` `release_drop_6cm` `no_table_rest_in_hold` `no_nonfoot_floor_support_in_hold` `feet_supported_in_hold` `fingertip_only_robot_contacts_in_hold` | 40 | 17.580000000001135（**17.58 s 即中止**） | `…/out/a2x_opp_index_1/result.json` |
| `a2x_preload10_1` | `--grip-preload-mm 1.5 → 1.0` | **true** | 126.8557675527 | 1.0603976650 | 无（20/20 绿） | 171 | 59.62800000002691 | `…/out/a2x_preload10_1/result.json` |
| `a2x_fgain2_1` | `--finger-gain 3 → 2` | **false** | −6.0130733727 | 131.8084432604 | `hold_7cm` `two_fingers` `no_support` `clearance_4cm` `slip_1cm` `release_drop_6cm` | 172 | 59.65600000002694 | `…/out/a2x_fgain2_1/result.json` |
| `a2x_lift12_1` | `--lift-height .15 → .12` | **true** | 100.1305607693 | 25.6648091184 | 无（20/20 绿） | 124 | 59.6240000000269 | `…/out/a2x_lift12_1/result.json` |
| `a2x_tfront23_1` | `--table-front .24 → .23` | **true** | 125.7953698877 | 0.0000000000 | 无（20/20 绿） | 127 | 59.6240000000269 | `…/out/a2x_tfront23_1/result.json` |
| `a2x_preload20_1` | `--grip-preload-mm 1.5 → 2.0` | **true** | 126.0455093991 | 0.2501395114 | 无（20/20 绿） | 128 | 59.59800000002687 | `…/out/a2x_preload20_1/result.json` |

**这 6 个 `a2x_*` 都是单变量臂，不是随机成功率样本。** 每臂的「只改 1 个 token」在启动前用
`diff <(tr ' ' '\n' <<< $FULL) <(tr ' ' '\n' <<< $变体)` 核验过：6/6 臂均 `ntokens_changed=2`
（即一行 `<` + 一行 `>`，恰好一个 token）。`Δ mm` 对单变量臂**不是**判据（P1 只约束 T1 复现臂），
它只是「换了变量之后 HOLD 抬升落到哪里」的读数。

### T1 判定明细

- **P1 PASS**：`a2rep327_1` `success=true`，`hold_min_lift_m = 0.1257953698876788` ⇒ 125.7953698877 mm，
  **Δ = 0.0000000000 mm ≤ 1.0 mm**。`gates` 20 门全 `true`，`fail_reason = null`。
- **P2 PASS**：`a2rep327_nogrip_1` `success=false`，6 门红，`hold_min_lift_m = -9.212e-05`（方块从未离桌），
  `hold_min_contact_bodies = 0`，`max_lift_m = 0.001854`。
- **P3 PASS（对照有效）**：两臂 `telemetry.csv.gz` 行数 29,812 vs 29,625（不同），表头相同；
  `cube_x_m/cube_y_m/cube_z_m` 三列 **`byte_identical = False`**，
  **首个分岔行 = 22366**（三列同一行开始分岔），最大绝对差
  `cube_x 0.031597981 m / cube_y 0.020935468 m / cube_z 0.143417146 m`；
  方块侧 6 个 result 标量中 4 个不同（`hold_min_lift_m`、`hold_slip_m`、`max_lift_m`、`hold_min_contact_bodies`），
  2 个相同（`max_drift_m`、`final_table_min_force_last100ms_N`，这两者与抓取无关）。
  ⇒ **前 22,366 行（DESCEND/ALIGN 阶段）逐字节相同、CLOSE 之后真实分岔**，
  与属主报告的「no-grip 闭手前精确一致、闭手后真实分岔且不抬起」同型。**不是**「两臂都成功」。
- **P4 PASS**：`base_fixture=false`、`free_base_exercised=true`、`body_action_override=false`、
  `peak_external_force=0.0`、`fixture_constraint=null`、`sonic_armature=false`、`passive_free_diagnostic=false`、
  `mujoco_version="3.2.7"`、`scene_generator_sha=2851290996…baa59165c`、
  `library_sha.sonic_v11=75815b28…300fef2`。两臂均满足。
- **与属主成功件的字段级对比（`raw/A2-METRICS.txt`，10 个关键字段全部 `equal=True`）**：

| 字段 | 属主 `w7_repeat327` | 本车道 `a2rep327_1` | equal |
|---|---|---|---|
| `success` | `true` | `true` | True |
| `hold_min_lift_m` | `0.1257953698876788` | `0.1257953698876788` | True |
| `hold_slip_m` | `0.006147586063486369` | `0.006147586063486369` | True |
| `max_lift_m` | `0.14332502505609868` | `0.14332502505609868` | True |
| `duration_s` | `59.6240000000269` | `59.6240000000269` | True |
| `gates`（20 门整块） | 全 true | 全 true | True |
| `final_table_min_force_last100ms_N` | `0.19619999999999996` | `0.19619999999999996` | True |
| `max_drift_m` | `0.0384718426134705` | `0.0384718426134705` | True |
| `final_pad_vertical_spread_m` | `0.002106413900284654` | `0.002106413900284654` | True |
| `right_arm_tracking_rms_rad` | `0.28696960683334877` | `0.28696960683334877` | True |

⇒ **不是「接近」，是 10/10 字段逐值完全相同**，与属主「该物理路径 run-to-run 逐位相同」的说法一致，
且这次是在**另一个进程、另一个目录、另一份复制、另一组 CPU（96-99）、另一个时刻**得到的。

### 扩展臂逐条读数

1. **`--opponent middle → index`：FAIL（硬失败，17.58 s 即中止）。**
   `fail_reason = "native branch static search rejected: No candidate passes static capture/hand/limits/open-table filters"`
   ⇒ 与属主 `w7_newtext43_327/314` 的失败模式**同一条**。原因：`native_branch.validate_candidates()`
   要求 7 个候选里至少一个满足 `capture_error_m ≤ .001` 且 `pad_spread_m ≤ .002` 且
   `minimum_arm_limit_margin_rad ≥ .02` 且 `open_robot_table_clearance_m ≥ .01` 且 `finger_replan_error_m ≤ .0015`；
   换成食指对向后，静态捕获几何无候选过关，直接抛 `NativeBranchRejected`， episode 提前结束、无 HOLD 窗。
   **结论：`--opponent middle` 不是可自由替换的旋钮，它是这条成功路径的必要条件之一。**
2. **`--finger-gain 3 → 2`：FAIL。** 跑完全程（`duration_s = 59.656`）但方块从未离桌：
   `hold_min_lift_m = -6.013 mm`、`max_lift_m` 同量级、`hold_min_contact_bodies` 掉到 0 级别，
   红门与负对照**完全同型**（`hold_7cm two_fingers no_support clearance_4cm slip_1cm release_drop_6cm`）。
   **结论：指增益 2 不足以夹持 35 mm 方块；`--finger-gain 3` 是断言域 `[1,3]` 的上界，也是成功所需。**
3. **`--grip-preload-mm 1.5 → 1.0`：PASS。** 20 门全绿，`hold_min_lift = 126.8558 mm`（比锚点高 1.060 mm）。
4. **`--grip-preload-mm 1.5 → 2.0`：PASS。** 20 门全绿，`hold_min_lift = 126.0455 mm`（Δ 0.250 mm）。
   ⇒ 预载在 **1.0 / 1.5 / 2.0 mm 三点都成功**，HOLD 抬升在 125.80–126.86 mm 窄带内。
   这是本车道唯一探到的**有裕度的**维度（但只有 3 个点，不构成成功率）。
5. **`--lift-height .15 → .12`：PASS。** 20 门全绿，`hold_min_lift = 100.1306 mm`。
   抬升随请求高度单调下移（120 mm 请求 → 100.1 mm 实测最低抬升），仍远高于 `hold_7cm` 门的 70 mm。
   注意这一臂 `Δ = 25.66 mm`，说明 **HOLD 最低抬升本身就是 `--lift-height` 的函数**，
   P1 的「≤1 mm」只对**冻结配方**有意义，不能拿来卡变体臂。
6. **`--table-front .24 → .23`：名义 PASS，但这是一个假阳性维度。** 20 门全绿、
   `hold_min_lift = 125.7953698877 mm`（Δ = 0），但方块侧三列 telemetry 与 T1 成功臂
   **逐字节相同**（29,812 行，`max_abs_diff = 0`），`result.json` 只有 10 个键不同：
   `runtime_stamp`、`scene`（路径名）、`wall_s`/`model_load_s`/`policy_median_ms`/`policy_p95_ms`/
   `execution_cycle_latency`（计时噪声）、`table_front_x_m`（0.24→0.23）、
   `table_placement_adaptation`（true→false）、`post_clearance_native_branch`。
   最后这个键里，7 个候选的 `open_robot_table_clearance_m` 全部变化
   （selected：0.05555757822975883 → 0.05055757822975883），
   但 **selected 的 `body_q` 逐位相同、`seed_label` 与 `branch_selected_time_s` 相同** ⇒ 执行物理完全一致。
   机制见 `table_placement.py`：`front=.23` 时写死 `pos='0.55 0 0.732' size='0.32 0.45 0.025'`，
   `front=.24` 时算出 `pos=0.555 size=0.315`，两者只是把桌前沿从 0.24 挪到 0.23；
   桌面高度 `table_top_z_m=0.757` 与后沿 `table_back_x_m=0.87` 不变，方块初始位姿不变，
   而成功路径要求机器人**全程不碰桌**（`no_robot_table_contact_full_task` 门），
   所以桌前沿在 `[.23,.245]` 内挪 1 cm 不进入任何接触判定。
   ⇒ **`--table-front` 在该区间不是有效物理变量；用它做「扩展维度」会得到无信息量的通过。**
   本车道把这一条作为发现报出，而不是当成第 5 个成功点。

---

## 七、失败与原因

**T1 主复现没有失败**（P1/P2/P3/P4 全 PASS），因此本节只记录扩展臂的失败，均为**预期内的探测结果**，
未做任何调参过线、未放宽任何闸门。

| 臂 | 失败门 / fail_reason | 一手原因 | 原始证据 |
|---|---|---|---|
| `a2x_opp_index_1` | 11 门红（含 `completed`）；`fail_reason = "native branch static search rejected: No candidate passes static capture/hand/limits/open-table filters"` | `native_branch.py:validate_candidates()` 的 5 条静态过滤在食指对向下无候选过关，抛 `NativeBranchRejected`，17.58 s 中止，无 HOLD 窗 | `raw/a2x_opp_index_1.stdout.log`（35,122 B，比正常 62 KB 短 ⇒ 提前结束）、`raw/a2x_opp_index_1.result.json` |
| `a2x_fgain2_1` | 6 门红：`hold_7cm two_fingers no_support clearance_4cm slip_1cm release_drop_6cm`；`fail_reason = null` | 指 KP 增益 2（KD = √2）不足以在 LIFT/HOLD 夹持 35 mm 方块，方块留在桌面；红门与 `--no-grip` 负对照同型 | `raw/a2x_fgain2_1.stdout.log`（62,210 B，跑完全程）、`raw/a2x_fgain2_1.result.json` |
| `a2rep327_nogrip_1` | 6 门红（同上）；`fail_reason = null` | **这是设计好的负对照**，`--no-grip` 下手指不闭合，方块不可能被抬起：`hold_min_lift_m = -9.212e-05`、`max_lift_m = 0.001854`、`hold_min_contact_bodies = 0` | `raw/a2rep327_nogrip_1.stdout.log`、`raw/a2rep327_nogrip_1.result.json` |

`a2_metrics.py` 首版有一个 `brief()` 里的 Python 运算符优先级 bug
（`'dict(...)' % v.get(...)[:40]` 对 bool 取切片 ⇒ `TypeError: 'bool' object is not subscriptable`），
在打印 `a2rep327_1` 的 `kinematic_outer_servo` 时抛出。**这是本车道自有工具的 bug，不是复现失败**；
已修（sha 由 `d1e10d11…` 改为 `2b449db8…`）并重跑，`raw/A2-METRICS.txt` 是修复后的完整版。
两版 sha 都在「凭证清单」里。

---

## 八、凭证清单

**复制完整性**
- `A2_sonicrep/COPY-MANIFEST.tsv` —— 888 行两件 sha256 比对（`SAME 881 / SELF_NEW 7 / DIFF 0`），
  头部含 `SRC=` / `DST=` / 10 条 `PRUNED_FROM_COPY:` 声明；生成于**任何一集启动之前**
- `A2_sonicrep/raw/A2-POSTRUN-VERIFY.tsv` —— 8 集跑完后重算（跳过 `out/a2rep*`、`out/a2x*`）：
  `files=888 SAME=881 SELF_NEW=7 DIFF=0` ⇒ 仿真未改动任何被复制的代码/权重/资产
- `A2_sonicrep/A2-PRUNE-LIST.txt` —— 6 件主动剪除文件的属主侧 sha256
- `A2_sonicrep/A2-CLOSURE.txt` —— 27 个本地模块闭包 + vendored 资产在场证明
- `A2_sonicrep/A2-IMPORT-PROBE.txt` —— `sonic_grasp.py --help` 全量输出，rc=0，零 ImportError，31/31 flag OK
- `A2_sonicrep/raw/SHA256SUMS.txt` —— `raw/` 内所有脚本本体 + 所有 run 产物的 sha256

**脚本本体 sha256（本地 ↔ 节点两端比对相同）**

| 脚本 | sha256 | 位置 |
|---|---|---|
| `run_own.sh` | `f4e2368f16544439f485ffd345a6de1ecfddb7ea4fc9dc78dfe70b99eedc4ccc` | `A2_sonicrep/run_own.sh`、`raw/` |
| `t1_driver.sh` | `03655b527c52a5350cda67d7e3f3ce406d9e0e2e51fcd099ca8c7d9075b44746` | `raw/`、`work/…/A2/` |
| `t2_driver.sh` | `d5cc27edaa57ca7b7caef44e80495b84ac2feeb8b3445a4ab18ae31ebfc2d064` | `raw/`、`work/…/A2/` |
| `t2b_driver.sh` | `f9684786de040207989c4896c957d589a8c709bc32d188574929c6a590f5eb50` | `raw/`、`work/…/A2/` |
| `closure.py` | `b288e6e24838a889717676d1a9ac4561f5b06c590a5c80066ea9d0d16b51890d` | `raw/`、`work/…/A2/` |
| `mk_manifest.py` v1（生成 `COPY-MANIFEST.tsv`） | `a497ad5acbddb66b91961129b708b8a33ec93d43f1551d66c124a626bb51a2c2` | `work/…/A2/`（已被 v2 覆盖） |
| `mk_manifest.py` v2（加 `--out/--skip-prefix/--self`，生成 `A2-POSTRUN-VERIFY.tsv`） | `cc1eb70971838f85c162e82631e25d74b14f00cb4cbb7992bba5eed63dfc6149` | `raw/`、`work/…/A2/` |
| `a2_metrics.py` v1（有 `brief()` bug） | `d1e10d11eb9c6097f6a84849c4d58f94b0d5ad51484b7e942bd78fd44c182021` | 已被 v2 覆盖 |
| `a2_metrics.py` v2（修复版，产出全部读数） | `2b449db81de7c3c10e27893ffc951f5fe751ba80f473576e02aca14e4114b8c5` | `A2_sonicrep/`、`raw/`、`work/…/A2/` |
| `FINDING.md`（终稿前快照） | 见 `raw/FINDING.snapshot-before-final.md` | `raw/` |

**每集 run 产物（`A2_sonicrep/raw/`，8 集齐全）**
- `<NAME>.stdout.log` —— 完整 stdout+stderr（含 `sonic_grasp.py` 末尾打印的 result JSON 全文）
- `<NAME>.meta.txt` —— `runner_sha256`、`sonic_grasp_sha256`、`versions=mujoco 3.2.7 numpy 1.26.4 ort 1.23.2 py 3.10.22`、
  CPU 集、`ulimit_v_KiB=16777216`、`timeout`、`nice`、完整 argv、前后 `/proc/pressure/{cpu,memory}`、`df`、`rc`、`wall_s`
- `<NAME>.result.json` —— `out/<NAME>/result.json` 的副本
- `A2-METRICS.txt` —— 8 集的谓词读数 + T1 两臂分岔检查 + 与属主成功件的 10 字段 diff + `table-front` 无效性分析
- `T1.driver.log` / `T2.driver.log` —— 驱动流水（含每臂 START/END 时间、单变量标签、降级说明、pressure/loadavg）
- `T1.driver.pid` / `T2.driver.pid` / `T2b.driver.pid`
- `out/<NAME>/` —— 每集完整原始产物：`result.json`、`telemetry.csv.gz`、`trajectory.npz`、
  `scene.xml`、`g1_free_grasp.xml`、`cube_contacts.csv.gz`、`cube_contact_steps.csv.gz`、
  `contact-audit.json`、`balance-audit.json`、`balance_contacts.csv.gz`、`robot_support_contacts.csv.gz`、
  `cycle-latency.csv.gz`、`calibration_geometry/`

**每集 `result.json.runtime_stamp`**：`mujoco_version`、`sys_executable`、`python_version`、
`model_sha.{scene,robot}`、`scene_generator_sha`、`library_versions.{numpy,onnxruntime}`、
`library_sha.*`（30 项）、`dt`。

---

## 九、未做与不可做

**不可做（纪律，全程遵守）**
- 调用属主 `run.sh` / `run.wave7.sh` / `ardy-grasp-run-*.sh` / `reserve_cpu_trial.py` / `snapshot_sources.py`
- 写 `reports/`；写 `/data/group4/20261006-093203-codex-6385a841/`（只读）；改 `repos/` `envs/` `weights/` `AGENTS.md`
- 调用任何台账写者：`journal_append.sh`、`close_ledger.sh`、`rebuild_index.sh`、`issue_append*.sh`、`rules_publish.sh`
- `scp` / `pip install` / `git push`；读 `~/.ssh/config`；碰私钥口令；本机（Windows）跑任何计算程序
- `pkill -f`（本车道唯一一次 kill 是 pid `2339311`，先核 `cmdline` + `Uid:1004` + `cwd`）

**未做**
- **MuJoCo 3.14.0 对照臂**：`mujoco314-only/` 已按指示排除，本车道只用 3.2.7。
  属主的 `w7_repeat314`（127.078 mm，True）与 `w7_nogrip314` 未复现。
- **演示视频导出**：`MUJOCO_GL=disable`；渲染需要 `ARDY_RENDER=1` + osmesa 库路径
  （属主 `run.sh` 里指向 `/home/group4/group4_dasc7606c/render_test/mesa_probe/…`），不在本车道判据内，未尝试。
  8 集的 `trajectory.npz` 均已留存，父会话若要出片可直接 replay（`render_verified_replay.py` 在复制里，未调用）。
- **`--motion-profile` 变体臂**：复制件与全部源 NPZ/CSV/summary 已就位，
  但属主侧两版（`w7_control43_327/314`）都失败于 `no_robot_table_contact_full_task`，本车道未重复消耗。
- **成功率**：本车道**没有**做随机/多 seed 池。8 集里 6 个是单变量点、2 个是 T1 固定配对，
  全部走同一条确定性物理路径（`a2rep327_1` 与属主件 10/10 字段逐值相同即为证）。
  **不能**把「5/8 成功」读成抓取成功率；它只是「这 6 个单变量点里 4 个通过」。
- **未探的合法维度**（P5 域内、本车道没花预算）：`--table-front .245`、`--finger-gain 1`、
  `--lift-height .07/.2`、`--capture-radius .005/.025`、`--contact-entry-dwell .02/.2`、
  `--close-seconds .25/2`、`--neutral-shoulder-offset -.2/.4`、`--grip-face-half-mm 6..15`、
  `--execution-speed-limit .5/3`、`--close-seconds`×`--contact-entry-dwell` 的组合。
  若父会话要扩池，建议优先 `--grip-preload-mm`（已见 1.0/1.5/2.0 三点全过，是唯一显示裕度的维度）
  与 `--lift-height`（已见 .12/.15 两点全过），并**避开** `--table-front`（纠正 7：无物理效果）
  与 `--opponent`（已证 index 会硬失败）。

**撤回名单遵守情况**：本文未引用 `36 mm 静态 15/15`、`40 mm 全零接触`、`60 mm 落地 0/15`、
`指间开口 12.1 mm`、`72.2/42.6 mm`、`pad 0/45` 中任何一个数字。
本文所有抓取几何数字均来自本车道 8 集的 `result.json` 或属主 `out/w7_*` 的 `result.json` 一手读取。
