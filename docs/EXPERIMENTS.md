# Experiments index

One row per run directory. Every number below is read out of the file named in the last column of
`docs/REPRODUCTION.md` §"Result table", or recomputed by `python tools/verify_repo.py` - not copied from a report.

| Directory | What it is | Entry point | Headline result, with its measurement rule | Tier |
|---|---|---|---|---|
| `src/sonic_v11_runtime/` | Shared runtime imported by three runs through `lib/` (SONIC v1.1 encoder wrapper, motion input, Unitree G1 MJCF, ARDY runtime source) | - | Contains `model_encoder.onnx` (50,117,796 B). `model_decoder.onnx` and the meshes are **not** in this repo | - |
| `experiments/cube35_wholehand_trial32/` | 35 mm cube, every finger in the physics, trial 01-32 series | `frozen32/start_frozen32.sh` | `success=true`, **22 gates all true**, `hold_min_lift_m = 0.08448322523549645`, `hold_slip_m = 0.0005198768604859854`, `max_lift_m = 0.12336126945999026`, 56,794 steps @500 Hz. Negative control: `max_lift_m = 0.0008600741240607501` | 1 |
| `experiments/cube80_sideways_wholehand/` | 80 mm cube, sideways approach, whole hand in physics | `execute_side.py` | `max_lift_m = 0.10857449062300661`, `hold_steps = 2500` (= 2.5 s at dt 1 ms); negative `success=false`, `max_lift_m = 0.001463928803046577`. The "14 repeated trajectory arrays are element-wise identical" claim is a boolean written by the runner itself; the arrays are not here, so it cannot be independently re-checked | 1, 2 |
| `experiments/batch_wholehand_360/` | 300 main + 60 ablation cells over cube size, position and gain | `execute_batch.py` (portable, one cell) / `batch_runner.py` (node scheduler) | Recorded `main_300 = 292 success`, `ablation_60 = 25`. This repo holds **353 of 360** per-cell `result.json`; recomputation reaches 288/23 and the gap is exactly the 7 absent cells. Group A = 100 *identical* configurations (`make_trials.py:19`) - a determinism check, not 100 independent samples | 2 |
| `experiments/w4_transfer_arms/` | Nine "W4" transfer arms: palm support, envelope, finger PD gains, substep/contact recipe, 80 mm variants | `ws4_migrate/rep_ext_<arm>/run_fixE.sh` | Under the 20-gate definition: **21 of 105 recorded cells are all-green** (per arm: base 3/6, cfg 0/12, comb 5/10, comb80 0/4, env 0/0, pd 3/9, phys 8/27, phys80 0/2, w1 2/35) | 1 |
| `experiments/kimodo_closed_loop_best/` | KIMODO-generated arm prior driven through the official SONIC grasp harness, free base, no pedestal, 35 mm free cube | `harness_nat2/run_cell.sh` | Cell `wb_kimo_p6l1`: `success=true`, **20/20 gates**, `gate_definition_version=5`, `max_lift_m = 0.1439862432245319`, `hold_min_lift_m = 0.13118074148281422`. Arm-level **3/6** segments. The deliverable README also quotes "+152.7 mm" from per-frame FK - a second ruler on the same cell; report both, never only the larger | 1 |
| `experiments/kimodo_generation_matrix/` | 17-cell KIMODO generation matrix + protocol | `scripts/` | Generation layer only (`cols=36`, 4.0 s -> 120 frames). No physics cell. Re-running the historical reference cell produced a different CSV hash: the upstream source tree has three uncommitted edits | 2 |
| `experiments/kimodo_input_gate/` | Evaluator and input gate that consumed the matrix above | `scripts/`, `bridge/motion_adapter/joint_contract.py` | All 17 cells rejected before the loop; every composite `success` false. The rejection is about column convention and root height, **not** a statement about generation quality | 2 (partial) |
| `experiments/kimodo_three_finger_envelope/` | Three-finger side envelope, CPU kinematic drive with real contact | `analysis*.py` | Uses its own gate set; its numbers are not comparable with the 20/22-gate runs | 1 |
| `experiments/tripod_50mm_negative/` | Three-finger tripod, 50 mm, negative result | `refs/from_shared_tree/tripod_50mm_negative/bin/replay_tripod.py` | 0/25. Note `physics_success:false` appears in planning-stage records while the top-level `success` field is the run gate | 1 |
| `experiments/tripod_iter01_91/` | Iterations 01-91 of the tripod line, one pass at iter91 | `refs/from_shared_tree/tripod_iter01_91/bin/replay_tripod.py` | One summary JSON per iteration, no arrays, no CSV: readable, not reproducible | 1 |
| `experiments/hand_jitter_analysis/` | SONIC v1.1 finger-jitter diagnostics | `*.py` | Source + result tables here; the `dense_trace.npz` per cell (~14 MB each) and the 635 MB evidence bundle are registered, not committed | 1 |
| `experiments/replay_videos_non_physical/` | Replay renders of the 35 mm trial32 trajectory | - | Rendered with `mj_step = 0`: visualisation of a recorded trajectory, **not** evidence of a rerun. The two mp4 files are byte-identical | - |
| `refs/cross_run/` | 151 files from 7 other runs | - | Included only where an artefact in this repo records the file's sha256 | - |
| `refs/from_shared_tree/` | 8 files that only existed in the node's shared tree | - | Includes both generations of `replay_tripod.py` (24,075 B and 57,429 B) | - |

## Reading rules that apply across the whole repo

1. **Gate sets are not one ruler.** The gate-count histogram over the 904 `result.json` files here is
   `{5:1, 6:2, 7:2, 12:50, 13:17, 16:18, 17:5, 20:322, 21:15, 22:17}`. The 20-gate harness definition
   (`gate_definition_version=5`), the 22-gate "real physical digit surfaces" set and
   `wholehand-v2-wristlocal-support` (the 12/13/16/17 groups) are three different standards.
   `experiments/batch_wholehand_360/GATES-v2.md` states explicitly that it does not replace the v5/v6 statistics.
2. **Physics versions differ.** `mujoco` versions across the artefacts are `{3.2.7: 840, 3.14.0: 44, unrecorded: 20}`.
   Comparing a 3.14.0 result with a 3.2.7 result is comparing different contact solvers.
3. **Sentinels exist.** `hold_min_lift_m = -1.0` / `-1000.0` and slip `1e12` mean "the hold window never opened",
   not a negative lift. `negative_trial32/result.json` has no `success` key at all, so `d["success"]` raises.
4. **The verdict field is the top-level `success` plus all gates true.** Ignore `*physics_success` and `legacy_*`.
