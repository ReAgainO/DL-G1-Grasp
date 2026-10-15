# steps-ws4 — 迁移对照实验的预备（子代理 ws4）

父会话 TASKID=20261008-221515-qoder-03c4673f（已认领，本文件不新建 claim）。
目标：确认 /data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/ 可被本会话独立复制并复跑 1 格 T1 锚点。
沙盒：/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/
纪律：源目录只读（一个字节不改）；跑格必须把 run_fixE.sh 的 BASE 指到自有副本，绝不写回源。

## [01] 探针（Step 0，必须先做）
命令: timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=10 S4000 'hostname; date "+%F %T"'
输出原文:
  worker00039
  2026-10-08 22:16:39
EXIT_CODE=0
判定: 退出码 0 且 hostname=worker00039 命中目标节点 -> 通过，继续执行。

## [02] 读运行方式（只读）
读取: README-fixE-7d11d1ae.md / README-copy-7d11d1ae.md / run_fixE.sh / drive_e35n.sh /
      drive_phase1..3.sh / jobs_phase1.txt / jobs_phase3.txt / jobs_e35n_all.txt /
      .flags_flat / b1_frozen_flags.txt / fixE_tally.py / progress.txt

### 这套 build 是什么
- rep_fixE = rep_b1（B1 时钟一致性 build）的副本；唯一源码改动 = reference_filter.py
  第 38 行 `if T>8:break` -> `if T>8.4:break`（实测: grep -n "T>" reference_filter.py -> 38:   if T>8.4:break）。
- 目的：让 T 序列 0.9*1.2^k 的最大尝试地平线从 6.687s 放宽到能覆盖 |目标-参考| 2.17-2.44 rad 的格，
  从而不再因 C2 滤镜冻结参考而 fallback 冻结。成功门/阈值未动。
- 上游来源链：rep_b1 = /data/group4/20261008-125638-qoder-d266d3a9/B1_clock 的副本（排除 out/e35n_*）。

### 跑一格的完整链路（实测自 run_fixE.sh 原文）
run_fixE.sh NAME EDGE CX CY FACE STEM CPUS
  1) BASE=/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE  (硬编码，复制后必须改)
     D=$BASE/rep  RAW=$BASE/raw
  2) PY=${S_PY:-/data/group4/20261004-205550-qoder-1280b420/env/bin/python}
     export PYTHONDONTWRITEBYTECODE=1 / OPENBLAS|OMP|MKL|NUMEXPR_NUM_THREADS=1
     TMPDIR=$D/tmp XDG_CACHE_HOME=$D/cache  MUJOCO_GL=disable  unset DISPLAY
  3) ulimit -v 16777216 (16GiB) ; cd $D  (= rep/)
  4) 门禁: out/$NAME 已存在 -> REFUSE exit3; NAME 仅 [a-z0-9_] -> 否则 REFUSE exit3
  5) 冻结 flags: mapfile -t S_FLAGS < $BASE/.flags_flat  (32 行)
  6) EXTRA=--cube-edge-mm/--cube-x/--cube-y (+ --grip-face-half-mm 仅当 FACE!=0)
  7) STEM!="-" 时 export N1_MOTION_STEM=$STEM
  8) 写 meta -> $RAW/$NAME.meta.txt (含 runner/sonic_grasp/native_branch/adaptive_hand/
     grasp_geometry 与 motion npz 的 sha256，host/uid/cpus/ulimit/PSI/df)
  9) timeout --foreground --kill-after=5s 900 taskset -c $CPUS nice -n 19 \
       "$PY" -B sonic_grasp.py "$NAME" "${S_FLAGS[@]}" --branch-coverage "${EXTRA[@]}" \
       > $RAW/$NAME.stdout.log 2>&1
 10) 计算 rc/wall -> 追加 meta；若有 out/$NAME/result.json 则 cp -a 到 raw/$NAME.result.json
 11) 追加一行 "$NAME rc=$RC wall=$WALL" -> $BASE/progress.txt
产物: rep/out/$NAME/{result.json,trajectory.npz,telemetry.csv.gz,...,g1_free_grasp.xml,scene.xml}
      以及 raw/$NAME.meta.txt, raw/$NAME.stdout.log, raw/$NAME.result.json

### tally 判据列（fixE_tally.py 实测）
- 扫描 BASE/rep/out/*/result.json，按 mtime >= CUT 过滤（默认 0=全部）
- 列: name, success=bool(r["success"]), fail=r["fail_reason"] 或空,
      lift=round(hold_min_lift_m*1000,1) mm, slip=round(hold_slip_m*1000,2) mm,
      red_n/red = [k for k,v in r["gates"].items() if not v] 的数量与名字
- 另有 fail=="approach native branch settling timeout" 单列；输出 fixE_tally.csv

### 单格驱动方式（drive_e35n.sh / drive_phase1..3.sh 实测）
- drive_e35n.sh: 读 jobs_e35n_all.txt (格式 NAME|EDGE|X|Y|FACE|STEM，6 列)，20 lanes 核 88..127，
  跳过 4 个对照格 (e35n_00_00|e35n_04_00|e35n_08_04|e35n_12_08)，pgrep -fc 限流，调 bash run_b1.sh。
  注意 drive_e35n.sh 调的是 run_b1.sh 且 BASE 指 d266 B1_clock 目录，是本目录的历史遗留，非 fixE 用。
- drive_phase1.sh: 6 格单发 (3 对照 + 2 frozen + 1 near-miss)，cores 16..27，调 run_fixE.sh
- drive_phase2.sh: grep -v 已跑 5 名后跑 jobs_phase2_remaining.txt，16 lanes cores 16..47
- drive_phase3.sh: 读 7 列 (NAME|EDGE|X|Y|FACE|STEM|ORDER)，跑 3 B1 对照 + 12 ws2 格，cores 48..77，
  并先把只有部分产物的 rep/out/<n> 移入 rep/out_broken_phase1/
=> 单格只需直接调 run_fixE.sh，不需要任何 drive 脚本。

## [03] 体积侦察与依赖清单（du -sh 实测）
rep_fixE 顶层:
  4.0K  drive_*.sh / run_*.sh / *.txt / .flags_flat / FINDING.md
  8.0K  fixE_tally.csv / jobs*.txt
  36K   pids/  raw_covoff_armA/
  28M   raw/                 (历史 meta/stdout/result 副本)
  1.5G  rep/                 <- 运行根
rep/ 内部:
  993M  out/                 (历史产物，跑格不需要)
  191M  sonic_v11/           (model_decoder.onnx 143M, model_encoder.onnx 48M, observation_config.yaml)
  114M  out_b1_keep/         (历史产物)
  90M   src/                 (g1 33M, ardy_runtime 54M, original_motions 1.5M, calibration.npz 432K, ...)
  52M   pydeps/              (onnxruntime 49M, yaml 2.9M, flatbuffers 108K)
  364K  out_broken_phase1/   (破碎产物)
  296K  official_refs/       (只读参考，非运行必需)
  236K  COPY-MANIFEST.tsv
  68K   sonic_grasp.py / 20K native_branch.py / 5K adaptive_hand.py / grasp_geometry.py
  + 数百个顶层 .py（历史 wave/checkpoint/analyze 脚本）

### 单格运行真正需要的依赖（code-read 证据）
| 依赖 | 出处（实测行号） | 用途 | 只读来源 |
|---|---|---|---|
| python 3.10.22 venv | run_fixE.sh PY 默认 | 解释器 | /data/group4/20261004-205550-qoder-1280b420/env |
| mujoco 3.2.7 + numpy 1.26.4 | env/bin/python -c 实测 | 物理仿真 | 同上（共享只读） |
| rep/ 顶层 .py | sonic_grasp.py:8-33 逐条 import | 控制栈 | 源 rep_fixE/rep/*.py |
| rep/pydeps | sonic_v11.py:15 sys.path.insert(ROOT/"pydeps") | onnxruntime 1.23.2 / flatbuffers / yaml | 源 rep_fixE/rep/pydeps |
| rep/sonic_v11/*.onnx | sonic_v11 策略加载 | SONIC v1.1 | 源 rep_fixE/rep/sonic_v11 |
| rep/src/g1 | sonic_grasp.py:47 assets=root/"src/g1" | scene_grasp_hand.xml 模板 | 源 rep_fixE/rep/src/g1 |
| rep/src/original_motions/<STEM>.npz+csv | sonic_grasp.py:172 | 参考动作输入 | 源（锚点用 new_motion_cube_a_s42） |
| rep/src/manual_grasp_calibration.npz | sonic_grasp.py:58 | 标定 | 源 rep_fixE/rep/src |
| $BASE/.flags_flat | run_fixE.sh:28 mapfile | 冻结 flags 32 行 | 源 rep_fixE/.flags_flat |
| env/bin/python 实体 | 软链实测 | 解释器实体 | /home/group4/.local/share/uv/python/cpython-3.10-linux-x86_64-gnu/bin/python3.10（/home 仅剩 4.7G，勿写） |

**不需要**: rep/out, rep/out_b1_keep, rep/out_broken_phase1（历史产物）；
src/ardy_runtime 与 src/*.csv 仅被历史生成脚本使用（grep 实测：ardy_runtime 只出现在
generate_wave7_text.py / native_generate.py，sonic_grasp.py 不引用）。
为避免遗漏导入闭合，复制策略为"整树排除 out*"，而不是逐件挑选。

## [04] 复制（cp -a/tar，源自只读）
目的地: /data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base/
（见下方实测输出）
