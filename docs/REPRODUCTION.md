# Reproduction guide

Three tiers, from "check the numbers" to "run the physics". Read §1 first and decide whether you
actually need tier 3 - most review work stops at tier 1.

## 1. Tier definitions

| Tier | What you can do | Requires |
|---|---|---|
| 1 - verify recorded results | hash every file, check the headline fields of every recorded cell, recount the transfer arms, check coverage of the 360-cell batch | Python 3.8+ only |
| 2 - recompute aggregates | re-run the batch summariser, regenerate the configuration pool, re-hash the generation matrix | Python + numpy 1.26.4 (see `requirements.txt`) |
| 3 - re-run the simulator | produce a fresh `result.json` | tier 2 + three classes of missing artefacts + the original path layout |

## 2. Tier 1

```bash
python tools/verify_repo.py          # 400-row sha sample, seconds
python tools/verify_repo.py --full   # all 11,021 files hashed
```

Checks performed, and what a healthy run looks like:

| Section | Meaning | Expected |
|---|---|---|
| `[manifest]` | every row of `EXPORT-MANIFEST.tsv` exists with the recorded size and hash | `missing=0 sizediffer=0 shadiffer=0` |
| `[layout]` | files and bytes per run directory | informational |
| `[headline]` | 14 field-level assertions on the four documented passes/negative controls | `all 14 assertions match` |
| `[gates]` | gate-count and MuJoCo-version histograms | `20/21/22 + 12/13/16/17` coexisting |
| `[w4-arms]` | per-arm tally under "top-level success and every gate true" | `TOTAL cells=105 all-gates-green=21` |
| `[batch]` | 360 planned vs present, `manifest.json` hash vs the recorded value | `present=353`, `PASS sha(manifest.json)` |
| `[deps]` | every sha recorded in a JSON here is either present or listed in `ASSETS-MANIFEST.tsv` | `unregistered=0` |

## 3. Tier 2

```bash
python3.10 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
bash tools/make_links.sh
python experiments/batch_wholehand_360/summarize_batch.py
```

`make_links.sh` is not optional for anything that imports the runtime: the runs do
`sys.path.insert(0, ROOT/'lib')` and git does not carry those links.

Known, explained difference: recomputation yields **288/300 and 23/60** against the recorded
**292/300 and 25/60**. The gap is the seven cells whose `result.json` no longer exists on the source
node either (`A000 B000 B051 C000 D000 NGF000 NWS000`); all 353 shared rows hash-match, and the
`summary.json` hash of `manifest.json` matches. Regenerating the pool: `make_trials.py` with the
documented numpy generator and seeds `20261009` / `20261010`.

## 4. Entry points per run

| Run | Entry | Notes |
|---|---|---|
| `cube35_wholehand_trial32` | `frozen32/start_frozen32.sh [NAME]` | verifies 735 frozen files by hash before launching; `MUJOCO_GL=disable` |
| `cube80_sideways_wholehand` | `execute_side.py`, planner `wholehand_side.py` | no shell wrapper; writes `logs/` entries |
| `batch_wholehand_360` | `execute_batch.py --plan plan_<ID> --name <ID>` (portable) | `batch_runner.py` is the node scheduler with node-only assertions |
| `w4_transfer_arms` | `ws4_migrate/rep_ext_<arm>/run_fixE.sh <NAME> <EDGE_MM> <CX> <CY> <FACE|0> <STEM|-> <CPUS>` | `rep_base/` has no `run_fixE.sh`; env vars `S_PY`, `W4C_PHYS`, `N1_MOTION_STEM` |
| `kimodo_closed_loop_best` | `harness_nat2/run_cell.sh` | `harness_s1000/` is only partially present (2 files) - see §6 |
| `kimodo_input_gate` | `bridge/motion_adapter/joint_contract.py` + `scripts/` | gate verdicts reproducible in principle; full 17/17 replay not verified in this session |
| `tripod_50mm_negative`, `tripod_iter01_91` | `refs/from_shared_tree/*/bin/replay_tripod.py` | two different generations of the same script name; they are not interchangeable |

`run_fixE.sh` hard-fails with `exit 3` (name exists / bad charset) or `exit 6` (empty `.flags_flat`)
before it ever reaches MuJoCo; those codes are the runner's own guards, not simulation errors.

## 5. Command -> expected field

```bash
python - <<'PY'
import json
p="experiments/cube35_wholehand_trial32/rep/out/normal_trial32/result.json"
d=json.load(open(p))
g=d["gates"]
print(d["success"], len(g), all(g.values()), d["hold_min_lift_m"], d["hold_slip_m"])
PY
# True 22 True 0.08448322523549645 0.0005198768604859854
```

Same shape for the other three headline cells; `tools/verify_repo.py` already asserts all 14 of them.

## 6. What stops tier 3, item by item

1. `model_decoder.onnx` 149,778,638 B, sha `34bae857...`: `sonic_v11.py:84` constructs the model and dies
   without it. Over GitHub's 100 MiB file limit and a weight, so it is registered in `ASSETS-MANIFEST.tsv`.
2. G1 meshes: 60 STL, 33,319,908 B. `model-assets.json` records 50 of them. Measured against the public
   `mujoco_menagerie` copy: **29 match, 17 differ, 4 absent** (`tools/mesh_source_comparison.tsv`).
   The differing files are the hand/head collision meshes, i.e. the geometry that carries contact.
3. `meshdir=/…/g1/meshes` is absolute in 79 MJCF files. Fixing the path changes the file hash, and the
   runs assert `runtime_stamp.model_sha` - so an edited scene is a different run, not a reproduction.
4. Node-only guards in `batch_runner.py`: rules-file hash assertion, `taskset` CPU pins 80-95,
   `>30 GiB` free space, `MUJOCO_GL=osmesa` plus an `LD_LIBRARY_PATH` into a task-specific OSMesa dir,
   `RLIMIT_AS` 4 GiB. On another machine, use the per-cell entry point instead of the scheduler.
5. Per-cell arrays (`trajectory.npz`, `dense_trace.npz`, ~14 MB each) are absent, so the per-frame
   evaluation of each gate cannot be recomputed here - only the recorded aggregates.
6. `cube35_wholehand_trial32` additionally needs a chain of `profile.npz` files, and its reader asserts
   the exact hash of those files; rebuilding them from the CSV sidecar would not satisfy the assertion.
7. `kimodo_closed_loop_best`: `harness_s1000/` reached this repo as 2 files; the deliverable
   `scene.xml`, `raw/` cells and `.flags_flat` for that harness are absent. Its results are verifiable,
   the harness is not re-runnable from here.

**Therefore**: tier 3 means restoring the original layout on the original machine (or an identical
one) using `tools/fetch_assets.sh` plus `docs/RUN_MAP.md`. Anyone claiming "clone and run" for these
grasps is overstating it.

## 7. Claims that are intentionally not restated as results

- Early KIMODO numbers (25/30 in place, +1.1994 m lift, 0.00803 m approach gap) were produced with a
  **weld equality constraint**; 44 of 55 "successes" had the hand more than 6 cm from the cube at weld
  time. The scripts and CSVs are kept as history, the conclusions are not.
- `106.5 mm wrist-to-cube minimum, zero contact` from the comparison note was an indexing artefact
  (body order vs slice offset) and its rig had the floating base removed.
- `0.1439862432245319` belongs to the KIMODO closed-loop cell, not to the 35 mm trial32 pass (which
  reports `max_lift_m = 0.12336...`). Two rulers on the same cell (gate max_lift 0.1440 m vs per-frame
  FK +152.7 mm) must be reported together.
- The renders under `replay_videos_non_physical/` were produced with `mj_step = 0`.
