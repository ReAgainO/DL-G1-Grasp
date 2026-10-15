# Troubleshooting

Entries are named by symptom. Run `python tools/verify_repo.py` first; items marked (V) are checked by it.

**`ModuleNotFoundError: sonic_v11` / `motion_input` on the first line**
The run inserts `<run>/lib` into `sys.path`, and git cannot carry symlinks. Fix: `bash tools/make_links.sh`
(or `--copy`). (V) `[deps]`/`[layout]` will not tell you this - it is an import-time failure.

**`bash: .../rep_base/run_fixE.sh: No such file`**
`run_fixE.sh` exists only in the eight `ws4_migrate/rep_ext_<arm>/` arms; `rep_base/` holds
`drive_e35n.sh`, `drive_phase{1,2,3}.sh`, `run_b1.sh`, `run_my.sh`.

**`REFUSE empty flag list`, exit code 6**
The runner reads `rep_ext_<arm>/.flags_flat` with `mapfile`. All nine flag files are in this repo, so
this error means you are in the wrong arm directory (`rep_ext_env` has no recorded cells) or you changed cwd.

**`FileNotFoundError: .../rep/out/generated_phases2/<stem>.npz`** (crash inside `sonic_grasp.py`)
These are **inputs**, not outputs; they look like generated data and were once excluded by a size rule.
They are in this repo. If one is still missing you will find its row in `ASSETS-MANIFEST.tsv`.

**Model construction fails / onnxruntime cannot find a file** (V `[deps]`)
`model_decoder.onnx` (149,778,638 B) is not shipped. See `tools/fetch_assets.sh`, route A.

**Robot appears without collision geometry, or MJCF fails to load** (V)
`meshdir` points at absolute source-node paths. Fetch the 60 STL files; do not substitute the public
mirror: 17 of the 50 recorded hashes differ and 4 files are absent there, all in hand/head links.

**`KeyError: 'success'` when reading `negative_trial32/result.json`**
That file has no `success` key (negative-control schema differs). Use `d.get("success")`.

**`hold_min_lift_m` is negative, e.g. `-1.0` or `-1000.0`**
Sentinel meaning "the hold window never opened", not a negative lift. Slip has its own sentinel `1e12`.
Real values appear in the headline cells; the `out_b1_keep` style directories in the 35 mm run are sentinel groups.

**`physics_success: false` looks like a failed run** (V `[headline]`)
Those occurrences are planning-stage records inside `selected_plan` / `joint_plan`. The verdict fields
are top-level `success` plus all gates true.

**`AssertionError: RULES_CHANGED_STOP_NEW_WORK`**
The batch scheduler hashes a governance file from the shared tree. That assertion cannot pass off-node;
run the per-cell entry `execute_batch.py` instead.

**`DATA_FREE_SPACE_BOUND`, or `taskset ... Invalid argument`**
Scheduler guards: >30 GiB free and CPU pins 80-95. Both are environment conditions, not bugs; use the
per-cell entry on smaller machines.

**Rendering fails with a GL/osmesa error**
Three different rendering setups exist across runs: `MUJOCO_GL=disable` (35 mm), `osmesa` plus a specific
`LD_LIBRARY_PATH` (batch), and a `envs/render` ffmpeg (80 mm). None of those paths is in this repo.

**Same command, different numbers between two machines** (V `[gates]`)
MuJoCo 3.2.7 and 3.14.0 both appear in these artefacts, and gate sets differ (20 vs 22 vs wholehand-v2).
Pin the version before interpreting.

**Recomputed batch counts are 288/23, but `summary.json` says 292/25** (V `[batch]`)
Seven cells' `result.json` files no longer exist even on the source node. The tool prints their ids.

**Video gates read 0/300 when recomputed, but the record says 300/300** (V `[deps]`)
Per-run replay mp4s are not shipped. Video-level claims cannot be verified from this repo.

**`UnicodeEncodeError: 'gbk' codec can't encode` (Windows)**
The tool forces UTF-8 output; if your terminal still objects, run
`PYTHONIOENCODING=utf-8 python tools/verify_repo.py`.

**A file in your checkout is ~100 bytes of text instead of the real artefact**
This repo does not use Git LFS, so pointer files cannot occur here. Compare against
`EXPORT-MANIFEST.tsv` column 4 (sha256) rather than trusting size - and re-run `verify_repo.py --full`.

**Release asset download returns 404/401**
A deploy key authenticates the Git protocol only; release assets are REST. Use a token with
`Contents: read`, or download in the web UI.

**Chinese-named files disappear from `git ls-files` output, or a tar list blows up**
`git -c core.quotepath=off ls-files -z` and `tar --null --files-from` with a NUL-separated list. Feeding
newline-separated names to `--null` yields one absurd filename.
