# A2 — 独立复制复现：ARDY 来源运动 → 官方 SONIC v1.1 身体目标 → 独立手指控制器

- 车道：A2　父会话 TASKID：`20261008-023143-qoder-d266d3a9`
- 节点：`worker00039`（`ssh S4000`），账号 `group4`（uid 1004）
- 本车道复制根（唯一可写大目录）：`/data/group4/20261008-023143-qoder-d266d3a9/A2_sonicrep`
- 属主只读源：`/data/group4/20261006-093203-codex-6385a841`
  —— **全程只读**；未调用 `run.sh` / `ardy-grasp-run-*.sh` / `reserve_cpu_trial.py` / `snapshot_sources.py`，
  未写属主 `out/`，未消耗其配额槽。
- 执行解释器：`/data/group4/20261004-205550-qoder-1280b420/env/bin/python`（未改动、未 pip install）

---

## verdict

**PENDING**（占位；T1 两臂跑完后改写，见文末「逐集数字表」）

---

## 判据（谓词）

在**任何一集启动之前**冻结，事后不得修改。判据只读 `result.json` 的 `success` 与 `gates`；
`rc`（进程退出码）**不是**成功位，只作为运行完整性记录。

- **P1 成功臂**：`result.json.success == true`，且
  `|hold_min_lift_m × 1000 − 125.7953698876788| ≤ 1.0 mm`
  （锚点值取自带 `runtime_stamp.library_sha.native_npz = 78eac68c…` 的属主成功件
  `out/w7_repeat327/result.json`；该物理路径在本节点已实测 run-to-run 逐位相同，故期望差 ≈ 0）
- **P2 负对照臂**：同一命令 + `--no-grip`，`result.json.success == false`
- **P3 两臂必须分岔**：两臂的**方块侧读数**（`telemetry.csv.gz` 的 `cube_x_m/cube_y_m/cube_z_m`
  三列 + `result.json` 的 `hold_min_lift_m, hold_slip_m, max_lift_m, max_drift_m,
  final_table_min_force_last100ms_N, hold_min_contact_bodies`）不得逐字节全同。
  若全同 ⇒ 判「**对照失效（缺陷）**」，如实报，**不得**当成「两臂都成功」。
- **P4 复现件自身完整性**（非成功位，但任一不成立则复现无效）：
  `base_fixture == false`、`free_base_exercised == true`、`body_action_override == false`、
  `peak_external_force == 0.0`、`fixture_constraint == null`、`sonic_armature == false`、
  `runtime_stamp.mujoco_version == "3.2.7"`、
  `runtime_stamp.scene_generator_sha == 28512909961057ab7f9c93144f633b5f0ca7f6b5aae9c1b05d80661baa59165c`、
  `runtime_stamp.library_sha.sonic_v11 == 75815b28521b43d96c9abf6a1ac546763ac9c384eda6b8dd6389d7c15300fef2`
- **P5 扩展臂**：只允许**单变量**改动，且改动必须落在 `sonic_grasp.py` 的 `assert` 合法域内。
  扩展臂结果**不是**随机成功率，只报「该单变量点通过/不通过」。
- 放宽任何闸门 = 本车道结论作废。T1 复现不出成功时**不调参去过线**，直接进「失败与原因」。

---

## 一、T1 锚点核对（先做，全部对上）

| # | 锚点 | 期望 | 实测 | 结论 |
|---|---|---|---|---|
| 1 | `sha256sum …/sonic_grasp.py` | 611 行 / 60,824 B | `28512909961057ab7f9c93144f633b5f0ca7f6b5aae9c1b05d80661baa59165c`，611 行 / 60,824 B | 一致 |
| 1 | `sha256sum …/adaptive_hand.py` | 4,139 B | `892bff4b931f9df1836d685b2cea0a233783f32cfdf8738e51cf41aeb038986f`，49 行 / 4,139 B | 一致 |
| 2 | `$PY -c "import mujoco,onnxruntime,numpy"` | `3.2.7 1.23.2 1.26.4 3.10.22` | **直接跑报 `ModuleNotFoundError: No module named 'onnxruntime'`** | 见「纠正 1」 |
| 2 | 同上，但先把 `<copy_root>/pydeps` 放进 `sys.path` | — | `mujoco 3.2.7 / numpy 1.26.4 / ort 1.23.2 / py 3.10.22 (Clang 22.1.3)` | 一致 |
| 3 | `out/w7_repeat327/result.json` 成功位 | `success=true` | `success = true`；`legacy_success = true`；`fail_reason = null`；`gates` 20 门全 `true` | 一致 |
| 3 | 「HOLD 最低抬升」真实键名 | ≈125.795 mm | 键名 **`hold_min_lift_m`**（单位 **米**），值 `0.1257953698876788` ⇒ **125.7953698876788 mm** | 一致 |
| 3 | `runtime_stamp.library_sha.sonic_v11` | `75815b28…0fef2` | `75815b28521b43d96c9abf6a1ac546763ac9c384eda6b8dd6389d7c15300fef2` | 一致 |
| 4 | `out/w7-source-binding/control-profile.json` | 1,739 B | 1,739 B，sha `81abc21545ba479745de28513519989b0c78c9e8cb10c31c4e5c0a42e2eea2f7`（由 `w7_control43_327/result.json.motion_profile.profile_sha256` 反证） | 一致 |
| 4 | `out/w7-source-binding/merged-source-summary.json` | 7,771 B | 7,771 B，sha `613e6e7ce10e24874bf0b25351c1c7414d6aa5e0ec056d58b4de97af834bce33`（= `control-profile.json.generation_summary_sha256`） | 一致 |

### 锚点 4：`control-profile.json` 引用的全部源文件（已一并复制）

| 角色 | NPZ | CSV | NPZ sha256 |
|---|---|---|---|
| reach | `out/w7-generated-text/w7_control_s43.npz` | `out/w7-generated-text/w7_control_s43.csv` | `62607734726d37cba47ef2b0c1c1fc53d0c2cc9200e6181a1b281376b01dc5b3` |
| lift | `out/generated_phases2/lift_s42.npz` | `out/generated_phases2/lift_s42.csv` | `d9c93e72977af4853041063bccd87665f1ebb727b9c8a4c1f3003b01cb2fcdf5` |
| hold | `out/generated_phases2/hold_s42.npz` | `out/generated_phases2/hold_s42.csv` | `4fc6a571e6661b9c345f5b1e669fbcd6d7713029e99d4b4c066dc5e0ad731096` |
| release | `out/generated_phases2/release_s42.npz` | `out/generated_phases2/release_s42.csv` | `961dbba514c4ce6e3c31c30a44f7d9e98451477fe03df37fd616f1a0a2b2bc57` |

外加 `generation_summary` = `out/w7-source-binding/merged-source-summary.json`，
它自己再引用 `out/generated_phases2/summary.json`（sha `a1555c93…`）、
`out/w7-generated-text/summary.json`（sha `171c1690…`）、`out/w7-generated-text/run.json`（sha `ac56d4da…`）。
⇒ 整个 `out/w7-source-binding/`、`out/generated_phases2/`、`out/w7-generated-text/` 三个目录**已整目录复制**。

---

## 二、对父会话假设的纠正（一手证据）

### 纠正 1 — `onnxruntime` 不在解释器的 site-packages 里，而在属主项目内的 `pydeps/`

`$PY -c "import onnxruntime"` **失败**（`ModuleNotFoundError`）。真实机制在 `sonic_v11.py:14-16`：

```python
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'pydeps'))
import onnxruntime as ort
import yaml
sys.path.insert(0,str(ROOT/'official_refs'))
from sonic_action_adapter import DEFAULT_ANGLES, I2M, M2I, ACTION_SCALE, KP, KD
```

⇒ **必须复制 `pydeps/`（52 MB，含 `onnxruntime 1.23.2` + `flatbuffers` + `yaml`）与 `official_refs/`（296 KB）**，
否则 `sonic_grasp.py` 连 import 都过不去。父会话的锚点 2 命令按原样写会误判「环境坏了」。

### 纠正 2（**关键**）— 成功件 `w7_repeat327` **没有**用 `--motion-profile`

父会话给的配方末尾带 `--motion-profile out/w7-source-binding/control-profile.json`。
一手证据说明这条 flag **不属于**成功配方：

- `out/w7_repeat327/result.json`：`"motion_profile": null`；
  `runtime_stamp.library_sha` 中 **`input_profile` / `generation_summary` 两个键 ABSENT**
  （`sonic_grasp.py:38` 只在 `selected_profile is not None` 时才写这两个键）；
  `runtime_stamp.library_sha.native_npz = 78eac68c405ceae93cb737b58022e83b5251d9d71def1eedb417caae0b73daff`
  = `src/original_motions/near_s42.npz`，即 `sonic_grasp.py:141` 的**默认 reach**分支；
  `result.source.source_npz` 也直接写着 `…/src/original_motions/near_s42.npz`。
- 真正带 `--motion-profile control-profile.json` 的两集**都是失败的**：
  `out/w7_control43_327/result.json` ⇒ `success=false`，红门 `no_robot_table_contact_full_task`，
  `hold_min_lift_m=0.1143338603328955`（114.334 mm）；
  `out/w7_control43_314/result.json` ⇒ `success=false`，同一红门，120.169 mm。
  两者的 `native_npz = 62607734726d…`（= `w7_control_s43.npz`），`input_profile = 81abc215…`。
- 属主自己的报告 `reports/20261006-093203-codex-6385a841-wave7-progress1-report.md`
  第三节表格第 2 行 `w7_repeat327 | 3.2.7 | 125.795 | 6.148 | 0.000000 | True`，
  第 4/6 行 `w7_control43_* | … | False`；第六节把 `--motion-profile` 单独列在**下一行**、
  且写明「`control-profile.json` **或** `newtext-profile.json`」——那是**可选变体**，不是成功配置的一部分。
- 负对照 `out/w7_nogrip314/result.json` 同样 `motion_profile = null`、`native_npz = 78eac68c…`。

⇒ **T1 复现命令 = 父会话的 flag 串去掉 `--motion-profile …`。**
带着它跑，复现出来的是 114.334 mm 的**失败**臂，与 P1 的 125.795 mm 相差 11.5 mm，必然判负。
`out/w7-source-binding/` 及其全部源文件**仍然照复制**（属主锚点 4 要求，且留作后续可选变体），
只是 T1 主复现不引用它。

### 纠正 3 — 扩展旋钮的合法域比父会话列的窄，`--table-front .22/.26` 与 `--finger-gain 4` 会直接 AssertionError

`sonic_grasp.py:582-604` 的断言（原文）：

```
assert .23<=a.table_front<=.245
assert a.table_front==.23 or a.direct_table
assert np.isfinite(a.finger_gain) and 1<=a.finger_gain<=3
assert .07<=a.lift_height<=.2
assert a.lift_height==.1 or a.grip_frame_lift
assert np.isfinite(a.grip_preload_mm) and .25<=a.grip_preload_mm<=2.5
assert a.grip_preload_mm==.5 or a.adaptive_hand
assert .005<=a.capture_radius<=.025
assert .02<=a.contact_entry_dwell<=.2
assert .25<=a.close_seconds<=2
assert -.2<=a.neutral_shoulder_offset<=.4
assert 6<=a.grip_face_half_mm<=15
assert a.grip_face_half_mm==15 or a.adaptive_hand
assert .5<=a.execution_speed_limit<=3.
assert 1<=a.arm_gain<=4 ; assert 1<=a.lift_damping<=4
assert 8<=a.align_seconds<=25 ; assert .01<=a.postcapture_servo_cap<=.06
```

- `--table-front .22` ⇒ **越下界**（0.23）；`--table-front .26` ⇒ **越上界**（0.245）。两者都跑不起来。
- `--finger-gain 4` ⇒ **越上界**（3）。跑不起来。
- 另注：`--opponent` 的 argparse **默认是 `index`**（`choices=['index','middle']`），
  成功配方显式给的是 `middle`；所以 `--opponent index` 是一个合法的**单变量**扩展点。
- 合法的扩展域（P5 可用）：`--table-front ∈ {.23, .245}`、`--finger-gain ∈ {1, 2}`、
  `--lift-height ∈ [.07, .2]`（≠.1 时必须保留 `--grip-frame-lift`）、
  `--grip-preload-mm ∈ [.25, 2.5]`、`--capture-radius ∈ [.005, .025]`、
  `--contact-entry-dwell ∈ [.02, .2]`、`--close-seconds ∈ [.25, 2]`、
  `--neutral-shoulder-offset ∈ [-.2, .4]`、`--opponent ∈ {index, middle}`、
  `--execution-speed-limit ∈ [.5, 3]`。

### 纠正 4 — `finger_clearance` 不是 `sonic_grasp.py` 的直接 import

`sonic_grasp.py:11-33` 直接 import 的本地模块里**没有** `finger_clearance`；
它是经 `adaptive_hand` / `clearance_approach` 间接进入闭包的，
同时被 `runtime_stamp` 的 sha 清单显式列出（`sonic_grasp.py:38`）。文件已复制，sha SAME。

### 纠正 5 — 输出目录由 `__file__` 决定，不由 `cd` 决定

`sonic_grasp.py:129`：`root=Path(__file__).resolve().parent; out=root/'out'/name; out.mkdir()`。
所以只要 `sonic_grasp.py` 在我的复制根里，输出就一定落在
`/data/group4/20261008-023143-qoder-d266d3a9/A2_sonicrep/out/<name>/`，**不可能**写进属主 `out/`。
`--motion-profile` 的相对路径也由同一个 `root` 解析（`motion_profile.py:MotionProfile(root, relative)`
＋ `bounded_path()` 会 `resolve()` 并断言 `is_relative_to(root)`，越界即 `ValueError`）。
`cd` 到复制根仍然照做（与属主纪律一致），但它不是决定性因素。
另：`out.mkdir()` 不带 `parents=True`，且**目录已存在会报错** ⇒ 每集必须用全新名字（`run_own.sh` 里也做了前置拒绝）。

### 纠正 6 — 复制时必须包含 `out/pinch-feasibility.json`

`--endpoint-seed` 会让 `runtime_stamp` 去 sha `root/'out/pinch-feasibility.json'`（`sonic_grasp.py:43`）。
这个文件在属主 `out/` 的**顶层**（10,339 B），不在任何 `w7_*` 子目录里。
若按「排除 out/ 下大 result 目录」一刀切，很容易把它一起排掉 ⇒ `FileNotFoundError`。已单独复制。
（`out/official-dynamics.json` 只有 `--sonic-armature` 才需要，成功配方不用；为完整性也复制了。）

---

## 三、清点与复制

`du -sh /data/group4/20261006-093203-codex-6385a841/*` 逐项体积（只读观测）：

```
2.7G  属主目录总计
1.2G  out/            （其中 1.19G 是 ~180 个历史 result 目录）
191M  sonic_v11/      （model_encoder.onnx 50,117,796 B + model_decoder.onnx 149,778,638 B + observation_config.yaml）
 89M  src/            （g1/ 33M 含 meshes、ardy_runtime/ 54M、original_motions/ 1.2M、manual_grasp_calibration.npz 424K）
 52M  pydeps/         （onnxruntime 49M + yaml 2.9M + flatbuffers）
 49M  uv-cache/        — 排除
 17M  source-snapshots/— 排除（属主快照器产物）
1.6M  cache/           — 排除
832K  tmp/             — 排除
296K  official_refs/   （sonic_action_adapter.py / ardy_mujoco_converter.py / g1_training.py / …）
8.0K  mujoco314-only/  — 排除（只切 MuJoCo 3.14 包，本车道只用 3.2.7）
1.23G 顶层 wave*.tar.gz 历史证据包 — 排除（先误复制，已删）
```

**实际复制内容**（`cp -a`，保持相对路径结构）：

- 顶层全部常规文件（`*.py` 173 个、`*.json`、`*.sh`），**除** `*.lock` / `wave*.tar.gz` /
  `wave*-summary.json` / `wave*-progress*.json` / `wave*-launches.jsonl` / `wave*-write-probe.bin`
- `sonic_v11/`、`pydeps/`、`official_refs/`、`src/` 四个目录整体
- `out/pinch-feasibility.json`、`out/official-dynamics.json`
- `out/w7-source-binding/`、`out/generated_phases2/`、`out/w7-generated-text/` 三个目录整体

**复制总体积：348,441,923 B = 332.3 MiB（`du -sb` 348,772,561 B / `du -sh` 335M）
⇒ 断言 ≤ 4 GB：PASS（用了 8.1%）。**

### 两端 sha256 逐件比对

`A2_sonicrep/COPY-MANIFEST.tsv`（生成脚本 `a2_metrics`/`mk_manifest.py`，见「凭证清单」）：

```
files=883  SAME=881  SELF_NEW=2  DIFF_or_UNEXPECTED=0  total_bytes=348441923 (332.3 MiB)
size_bound_4GiB=PASS
```

- **DIFF = 0**（883 件里 881 件与属主原件 sha256 + 字节数双同；2 件 `SELF_NEW`
  是本车道自写的 `A2-CLOSURE.txt`、`A2-PRUNE-LIST.txt`）。
- 关键件复核：`sonic_grasp.py` sha `2851290996…baa59165c` SAME；
  `adaptive_hand.py` sha `892bff4b93…38986f` SAME；
  `sonic_v11/model_decoder.onnx` 149,778,638 B SAME；`model_encoder.onnx` 50,117,796 B SAME。

### 主动剪除（`A2_sonicrep/A2-PRUNE-LIST.txt`）

以下 6 件**故意不复制**：它们硬编码属主 task id，一旦被误调用会写属主目录 / 消耗属主配额槽。
剪除前先记录其属主侧 sha256：

| 文件 | 属主侧 sha256 | 原因 |
|---|---|---|
| `run.sh` | `86db3c2e0ffea07b9965c01a03da1ee1b0aebeaa52a363fabec0269fe80af7f5` | 内含 `rules_sha` 断言 + `reserve_cpu_trial.py` 闸 + 写属主 `logs/…/steps.md` |
| `run.wave7.sh` | 同上（与 `run.sh` 同内容） | 同上 |
| `ardy-server-entry.sh` | `ccb6e1c7cdb9352955a2dad5a1e17c3a033d94d82021a08a561b8c7604a8e906` | `simulate` 子命令直接 `exec bash run.sh` |
| `ardy-server-entry.wave7.sh` | 同上 | 同上 |
| `reserve_cpu_trial.py` | `00a24fbc31a3a1378a0e50ad757063156292c45ea19b5541721f2cf451605d66` | 属主私有配额闸本体 |
| `snapshot_sources.py` | `8cdbb9e2f6d8b7d8b5cb893a4b3f270f1243763c79f38bfd6ff41797b734952e` | 属主快照写者 |

这 6 件都**不在** `sonic_grasp.py` 的 import 闭包里（见下），剪除对复现零影响。
其余 147 个不可达的 `.py`（`checkpoint_*`、`record_progress`、`begin_wave*`、`incremental_*_git`、
`deploy_wave7_*`、`wave*_records` 等台账/记录写者）**保留但绝不调用**。

---

## 四、import 闭包检查

脚本 `work/…/A2/closure.py`（AST 递归 BFS，只读），输出存 `A2_sonicrep/A2-CLOSURE.txt`：

```
CLOSURE_LOCAL_MODULES(27)  —— 全部存在，缺失 0
  adaptive_hand  balance_audit  branch_execution  branch_face_ik  clearance_approach
  contact_audit  cycle_latency  decoded_arm_filter  discrete_reference  execution_monitor
  finger_clearance  finger_control  grasp_geometry  motion_input  motion_profile
  native_branch  neutral_pose  policy_reference  reference_filter  setdown_plan
  sonic_action_adapter(official_refs/)  sonic_grasp  sonic_v11  source_physics_core
  table_placement  task_plan  trajectory
EXTERNAL_TOPLEVEL(17): argparse collections csv gzip hashlib json math mujoco numpy
                       onnxruntime os pathlib subprocess sys time xml yaml
VENDORED OK: pydeps/onnxruntime/__init__.py (14,874 B), pydeps/yaml/__init__.py (12,311 B),
             sonic_v11/model_encoder.onnx (50,117,796 B),
             sonic_v11/model_decoder.onnx (149,778,638 B),
             sonic_v11/observation_config.yaml (2,475 B)
TOPLEVEL_PY_TOTAL=173  REACHABLE=26  UNREACHABLE_FROM_ENTRY=147
```

实跑 import 探针（`A2_sonicrep/A2-IMPORT-PROBE.txt`，与 `run_own.sh` 完全相同的环境导出）：

```
cd <copy_root>; ulimit -v 16777216; taskset -c 0-3 \
  $PY -B sonic_grasp.py --help
probe_rc = 0    输出 4,190 B / 106 行
grep -c "ImportError|Traceback|ModuleNotFoundError|No module named" = 0
31/31 配方相关 flag 在 --help 里全部 OK，MISS = 0
```

⇒ **零 ImportError，零缺件，未改任何代码。**

---

## 五、我自己的 runner

`A2_sonicrep/run_own.sh`（sha256 `f4e2368f16544439f485ffd345a6de1ecfddb7ea4fc9dc78dfe70b99eedc4ccc`，3,404 B）
照抄属主 `run.sh` 的物理相关导出，去掉配额闸与 rules_sha：

```
PY=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
TMPDIR=<copy_root>/tmp  XDG_CACHE_HOME=<copy_root>/cache  MUJOCO_GL=disable
unset PYOPENGL_PLATFORM ; unset DISPLAY
ulimit -v 16777216        # 16 GiB AS
cd <copy_root>            # 属主纪律，虽然 root 实际由 __file__ 决定
timeout --foreground --kill-after=5s ${A2_TIMEOUT:-900} taskset -c ${A2_CPUS} nice -n 19 $PY -B sonic_grasp.py <NAME> …
```

每集把 stdout/stderr 落 `raw/<NAME>.stdout.log`、环境/时间/版本/压力落 `raw/<NAME>.meta.txt`、
`result.json` 复制一份到 `raw/<NAME>.result.json`。
输出名已存在时**前置拒绝**（rc=3），避免踩 `out.mkdir()`。

节点状态（开工前）：`nproc=128`，`/proc/pressure/cpu some avg10=0.00 avg60=0.00 avg300=0.00`
⇒ **未触发「降到 ≤2 并发」条件**，按 ≤4 并发、每集 4 CPU、互不重叠的 CPU 集执行；`nice -n 19`。
本车道实际最多同时 2 集（T1 两臂），CPU 集 `96-99` / `100-103`。

---

## 六、T1 复现命令（冻结）

成功臂（`a2rep327_1`）——父会话 flag 串**去掉 `--motion-profile`**（见纠正 2）：

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

负对照臂（`a2rep327_nogrip_1`）＝同一命令 + `--no-grip`。

配方逐 flag 与属主成功件回显字段的对照（全部来自 `out/w7_repeat327/result.json`，非推测）：

| flag | 属主成功件回显 |
|---|---|
| `--strict-execution` | `strict_execution_gate_enabled = true` |
| `--finger-gain 3` | `independent_finger_kp_gain = 3.0`（`kd = 1.7320508…` = √3） |
| `--grip-preload-mm 1.5` | `grip_preload_mm = 1.5`，`adaptive_hand.geometric_pad_preload_m = 0.0015` |
| `--table-front .24` | `table_front_x_m = 0.24000000000000005` |
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
| `--endpoint-seed --endpoint-seed-native` | `endpoint_branch_loaded = true`，`endpoint_seed` sha 入 `library_sha` |
| `--contact-close` | `preclosure_contact_close_enabled = true` |
| `--contact-entry-dwell .04` | `preclosure_contact_dwell_s = 0.04` |
| `--gravity-arm 1` | `right_arm_gravity_feedforward_scale = 1.0` |
| `--opponent middle` | `opposing_pad = "right_middle_fingertip"` |
| `--close-seconds .5` | `close_command_duration_s = 0.5` |
| `--neutral-shoulder-offset .2` | `neutral_shoulder_offset_rad = 0.2` |
| `--clearance-approach` | `clearance_approach` dict 存在（`actual_wrist_clearance_z_m = 0.9`） |
| `--clearance-native-branch` | `post_clearance_native_branch_enabled = true` |
| `--clearance-branch-servo` | `post_clearance_branch_servo_enabled = true` |
| （无 `--motion-profile`） | `motion_profile = null`，`native_npz = 78eac68c…`（`near_s42.npz`） |
| （无 `--no-grip`） | `no_grip = false` |
| 其余全部取 argparse 默认 | `weight=.03 / align_seconds=8 / arm_gain=1 / lift_damping=1 / reference_margin=.002 / postcapture_servo_cap=.06 / execution_speed_limit=2 / grip_face_half_mm=15 / finger_table_clearance_mm=0` —— 与成功件回显逐一相符 |

属主成功件墙钟 `wall_s = 115.43`、仿真时长 `duration_s = 59.624` ⇒ 单集约 2 分钟，`timeout 900` 余量充足。

---

## 七、逐集数字表

（跑完追加）

| 名字 | 变量 | success | HOLD 最低抬升 mm | \|Δ\| vs 125.7954 mm | 失败门 | 墙钟 s | result.json 绝对路径 |
|---|---|---|---|---|---|---|---|
| _待填_ | | | | | | | |

---

## 八、失败与原因

（若 T1 复现不出成功则填此段：完整 stdout/stderr 路径、`gates` 红门、`fail_reason`、
与属主成功件的 10 个关键字段级 diff。**不放宽闸门、不调参过线。**）

_待填_

---

## 九、凭证清单

- `A2_sonicrep/COPY-MANIFEST.tsv` —— 883 行两件 sha256 比对（SAME 881 / SELF_NEW 2 / DIFF 0），
  头部含 `SRC=` / `DST=` / 10 条 `PRUNED_FROM_COPY:` 声明
- `A2_sonicrep/A2-CLOSURE.txt` —— 27 个本地模块闭包 + vendored 资产在场证明
- `A2_sonicrep/A2-IMPORT-PROBE.txt` —— `sonic_grasp.py --help` 全量输出，rc=0，零 ImportError
- `A2_sonicrep/A2-PRUNE-LIST.txt` —— 6 件主动剪除文件的属主侧 sha256
- `A2_sonicrep/run_own.sh` —— sha256 `f4e2368f16544439f485ffd345a6de1ecfddb7ea4fc9dc78dfe70b99eedc4ccc`
- `A2_sonicrep/a2_metrics.py` —— sha256 `d1e10d11eb9c6097f6a84849c4d58f94b0d5ad51484b7e942bd78fd44c182021`
- `work/20261008-023143-qoder-d266d3a9/A2/closure.py` —— sha256 `b288e6e24838a889717676d1a9ac4561f5b06c590a5c80066ea9d0d16b51890d`
- `work/20261008-023143-qoder-d266d3a9/A2/mk_manifest.py` —— sha256 `a497ad5acbddb66b91961129b708b8a33ec93d43f1551d66c124a626bb51a2c2`
- 上述 4 个脚本均已 `cat 本地 | ssh 'cat > 远端'` 传输并两端 sha256 比对相同
- 每集：`raw/<NAME>.stdout.log`、`raw/<NAME>.meta.txt`（含 runner sha / sonic_grasp sha /
  mujoco·numpy·ort·py 版本 / CPU 集 / ulimit / 前后 `/proc/pressure` / `df`）、`raw/<NAME>.result.json`
- `runtime_stamp`（每集 result.json 内）：`mujoco_version`、`sys_executable`、`python_version`、
  `model_sha.{scene,robot}`、`scene_generator_sha`、`library_versions`、`library_sha.*`、`dt`

## 十、未做与不可做

- **不可做**：调用属主 `run.sh` / `ardy-grasp-run-*.sh simulate` / `reserve_cpu_trial.py` /
  `snapshot_sources.py`；写 `reports/`；写 `/data/group4/20261006-093203-codex-6385a841/`；
  改 `repos/` `envs/` `weights/` `AGENTS.md`；调用任何台账写者
  （`journal_append.sh` `close_ledger.sh` `rebuild_index.sh` `issue_append*.sh` `rules_publish.sh`）；
  `scp` / `pip install` / `git push`；本机跑计算。
- **未做**：MuJoCo 3.14.0 对照臂（`mujoco314-only/` 已按指示排除，本节点本车道只用 3.2.7）；
  演示视频导出（`MUJOCO_GL=disable`，渲染需 `ARDY_RENDER=1` + osmesa 库路径，不在本车道判据内）；
  `--motion-profile` 变体臂（已知属主侧两版都失败于 `no_robot_table_contact_full_task`，
  复制件已就位，父会话若要可另开）；SETDOWN / 全身 COM-COP / 实机 / 视觉定位。
- 撤回名单已遵守：本文未引用 `36 mm 静态 15/15`、`40 mm 全零接触`、`60 mm 落地 0/15`、
  `指间开口 12.1 mm`、`72.2/42.6 mm`、`pad 0/45` 中任何一个数字。
