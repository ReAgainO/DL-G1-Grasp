# RUNBOOK — rep_fixE 独立复跑（ws4）

- 任务：20261008-221515-qoder-03c4673f（子代理 ws4，迁移对照实验预备）
- 结论：**可独立复跑**。1 格 T1 锚点 `e35n_00_06` rc=0 wall=162s，success=True，
  tally 行与源 `fixE_tally.csv` **逐字节相同**；8 个物理数组 1593 帧与源**逐位相同**。
- 复跑副本：`/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base`（361M，1243 文件）
- 源目录 `/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE` 全程**只读**（后文有证明）。

---

## 1. 环境事实（实测）

| 项 | 值 |
|---|---|
| 节点 / hostname | worker00039 |
| 共享 venv | `/data/group4/20261004-205550-qoder-1280b420/env/bin/python` |
| python | 3.10.22（软链到 `/home/group4/.local/share/uv/python/cpython-3.10-linux-x86_64-gnu/bin/python3.10`） |
| mujoco / numpy | 3.2.7 / 1.26.4 |
| onnxruntime | 1.23.2（来自 `rep_base/rep/pydeps`，非共享 venv） |
| 资源纪律 | `taskset` 2 核 + `nice -n 19` + `ulimit -v 16777216`（**run_fixE.sh 内置**）、`PYTHONDONTWRITEBYTECODE=1` |
| 磁盘 | /data 11T 可用（大件都写这里）；**/home 仅剩 4.7G，勿写 TMPDIR/XDG_CACHE_HOME 到 /home** |
| 机器常态 | load ~82 / 128 核（他人 100+ 仿真在跑），跑格前需挑空核 |

---

## 2. 一次性复制（从只读源）

```bash
SRC=/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base
mkdir -p "$DST" && cd "$SRC" || exit 2
tar --exclude='./rep/out' --exclude='./rep/out_b1_keep' --exclude='./rep/out_broken_phase1' \
    --exclude='./rep/cache' --exclude='__pycache__' -cf - . | (cd "$DST" && tar -xf -)
# 实测: 0.7s, 361M, 1243 文件, 与源 sha256 全树一致
```

### 2.1 【关键坑】`rep/out` 不是纯历史产物 —— 必须补 3 个运行期输入

第一次照"排除 out"复制后跑格 **必崩**（实测 attempt1：rc=1, wall=3s）：

```
FileNotFoundError: [Errno 2] No such file or directory:
  .../rep/out/generated_phases2/lift_s42.npz     # sonic_grasp.py:183 (--phase-clips 路径)
```

`sonic_grasp.py` 直接读 `rep/out/` 下的输入缓存：
- `out/generated_phases2/{lift,hold,release}_s42.npz(+.csv)` — :183，必需
- `out/pinch-feasibility.json` — :43（stamp）与 :262（`--endpoint-seed` 生效时），必需
- `out/official-dynamics.json` — :42 与 :70（仅 `sonic_armature` 时），为保险一并复制

```bash
mkdir -p "$DST/rep/out"
cp -a "$SRC/rep/out/generated_phases2" "$DST/rep/out/"
cp -a "$SRC/rep/out/official-dynamics.json" "$SRC/rep/out/pinch-feasibility.json" "$DST/rep/out/"
# 实测 12 个文件 sha256 全部 OK（lift/hold/release 的 npz+csv、summary.json、run.json、jobs.json、generation.log、2 个 json）
```
其余 83 个 `rep/out/<cell>/` 确属历史产物，不必复制（源 `out/` 共 86 项 = 83 格 + 上述 3 项）。
`src/ardy_runtime/`(54M) 与 `src/*.csv` 仅被历史生成脚本用，本链路不需要，但为免漏依赖已整树保留。

### 2.2 把 BASE 指向自有副本（**必做，否则会写源**）

`run_fixE.sh` / `fixE_tally.py` / `drive_*.sh` 全部硬编码源路径。其中
`fixE_tally.py` 会**覆盖源 `fixE_tally.csv`**，`drive_*.sh` 会往源目录写 `pids/*.launch.log`。

```bash
sed -i "s#^BASE=$SRC\$#BASE=$DST#" "$DST/run_fixE.sh"
sed -i "s#^BASE = Path('$SRC')#BASE = Path('$DST')#" "$DST/fixE_tally.py"
for f in drive_phase1.sh drive_phase2.sh drive_phase3.sh drive_e35n.sh run_b1.sh run_my.sh; do
  sed -i "s#$SRC#$DST#g" "$DST/$f"
done
# 保留源 meta 供对拍：把复制来的 raw/ 改名，再建空 raw/ 与空 out/
mv "$DST/raw" "$DST/raw_src_snapshot"; mkdir -p "$DST/raw" "$DST/rep/out"
```

---

## 3. 跑一格（可粘贴）

参数顺序 = `NAME EDGE CX CY FACE STEM CPUS`；前 6 列直接取自 `jobs_e35n_all.txt`（第 7 行即锚点）：

```bash
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base
L=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/logs; mkdir -p "$L"
cd "$DST" || exit 2
nohup bash run_fixE.sh e35n_00_06 35 0.266000 -0.127600 0 new_motion_cube_a_s42 70,71 \
  > "$L/anchor.launch.log" 2>&1 &
```

- CPUS 要挑**空核**（机器满载）。选核（纯 python，不需 awk）：
  ```bash
  python /data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/ws4_idle.py
  # 实测 57 核空闲，取 cpu70,71
  ```
- 轮询（单条 ssh ≤10 分钟）：
  ```bash
  t0=$(date +%s); while [ $(( $(date +%s) - t0 )) -lt 420 ]; do
    [ -f $DST/rep/out/e35n_00_06/result.json ] && { echo DONE; break; }; sleep 15; done
  ```
- **REFUSE 语义**：`rep/out/<NAME>` 已存在 → exit 3。重跑前必须先把旧目录挪走：
  ```bash
  mkdir -p $DST/rep/out_broken_ws4 && mv $DST/rep/out/<NAME> $DST/rep/out_broken_ws4/
  ```

产物位置：
```
$DST/rep/out/<NAME>/result.json|trajectory.npz|telemetry.csv.gz|cube_contacts.csv.gz|scene.xml|g1_free_grasp.xml|...
$DST/raw/<NAME>.meta.txt|.stdout.log|.result.json      # meta 含 runner/sonic_grasp/... 的 sha256、cpus、ulimit、PSI、df
$DST/progress.txt                                      # 追加 "<NAME> rc=.. wall=.."
```

## 4. 判定（tally 判据列）

```bash
cd "$DST" && PYTHONDONTWRITEBYTECODE=1 python fixE_tally.py 0
# 实测输出：
# fixE stratum (mtime>0.0): total=1 success=1
#   SUCCESS e35n_00_06 lift= 104.3 slip= 3.7
# 写入 $DST/fixE_tally.csv: e35n_00_06,True,,104.3,3.7,0,
```
判据列（`fixE_tally.py` 实测）：`name, success=bool(r["success"]), fail=r["fail_reason"],
lift_mm=round(hold_min_lift_m*1000,1), slip_mm=round(hold_slip_m*1000,2), red_n/red = r["gates"] 中 False 的个数/名字`。
tally 只按 `mtime>=CUT` 过滤 `rep/out/*/result.json`，与墙钟量无关。

---

## 5. 坑清单（全部实测）

1. **`rep/out/generated_phases2` 是必需输入**（见 2.1）；只按体积排除 out/ 会 100% 崩在 sonic_grasp.py:183。
2. **tally/drive 脚本硬编码源 BASE**：tally 会覆盖源 `fixE_tally.csv`，drive 会写源 `pids/`。复制后必须逐条 sed（2.2）。
3. `drive_e35n.sh` 调的是 `run_b1.sh` 且 BASE 指 d266 `B1_clock` 目录 —— 是历史遗留，**不是 fixE 链路**，别拿它跑 fixE。
4. `run_fixE.sh` 的 `nice -n 19`/`ulimit -v`/线程数 env 都内置了；不要在外面重复设 TMPDIR 到 /home（只剩 4.7G）。
5. 机器满载（load 82/128）：wall 从源 137s 变 162s，**但对结果零影响**（物理数组逐位相同）。
6. `out/<NAME>/g1_free_grasp.xml` 第 2 行 `meshdir` 是绝对路径 → 换目录后该文件 sha 必变（实测仅 1 行不同），不影响物理；`scene.xml` sha 不变。
7. 重跑同格必须先挪走 `rep/out/<NAME>`，否则 exit 3 REFUSE。
8. 单条 ssh 别跑 >10 分钟：用 nohup + 轮询（本格 162s，但满载时可能更久）。

---

## 6. W4 批量跑法（模板，本次未执行）

本会话纪律 ≤4 进程：把 drive 脚本里的 `-ge 16/-ge 20` 限流改成 `-ge 4`，核按当时空核分配：

```bash
DST=/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base
L=$DST/../logs; cd "$DST" || exit 2
i=0
while IFS='|' read -r n e x y f s; do
  [ -z "$n" ] && continue
  while [ "$(pgrep -fc '[r]un_fixE.sh')" -ge 4 ]; do sleep 5; done
  c=$((70+(i%4)*2)); i=$((i+1))
  nohup bash run_fixE.sh "$n" "$e" "$x" "$y" "$f" "$s" "$c,$((c+1))" >> "$L/batch.launch.log" 2>&1 &
done < jobs_e35n_all.txt
wait; python fixE_tally.py 0 | tail -20
```

---

## 7. 源目录只读证明（实测，收尾时复核）

```
run_fixE.sh      sha256 3ae8ae7cc389505e08845addbb95d389526e5d2f1597a6f122ae0b4d39053959  (与源 meta 中的 runner_sha256 一致)
fixE_tally.py    sha256 caa76d6aeed21f9ab4c20e66603f81525a0e9ca6656ea605506e8d66dcfee20d
fixE_tally.csv   sha256 ff08f390f26e5a578e62daebbbd9a689fe6d7195fd45a93d5e4040e9534bab81  mtime 18:47:03 (未变)
rep/out/         86 项, newest=e35n_16_19 (18:43:37)      raw/ 350 项, newest 18:43:37
<src>/rep/out/e35n_00_06 mtime 18:34:08 (未被本次运行触碰)
```
