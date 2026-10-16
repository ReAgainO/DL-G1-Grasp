# DL-G1-Grasp — humanoid whole-hand grasping in MuJoCo

This repository contains the code of grasping schemes that succeeded, together with everything needed
to check and repeat them. An arm prior from motion generation (KIMODO / ARDY) is closed in simulation
by the SONIC v1.1 policy with **every finger inside the physics**: a Unitree G1 with a 3-finger hand
lifts free cubes of 35 mm and 80 mm off a table, and each attempt is recorded against an explicit gate
set. For each scheme you get the simulation scenes (MJCF), the run inputs, the machine-readable results
(`result.json` per cell), and step-by-step reproduction instructions in §3.

Model weights and vendor SDKs are not part of the repo; anything else a run needs is registered with
its sha256 in [`ASSETS-MANIFEST.tsv`](ASSETS-MANIFEST.tsv) - see §5.

---

## Demo videos

| Experiment | Video | Caliber |
|---|---|---|
| 35 mm whole hand (trial32, 22 gates green) | [normal_trial32.mp4](experiments/replay_videos_non_physical/videos/normal_trial32.mp4) | replay render of the recorded trajectory (sha in the manifest alongside) |
| 80 mm sideways (108.574 mm / 2.5 s) | [grasp.mp4](experiments/cube80_sideways_wholehand/out/side80_native3/replay_clean/grasp.mp4) | same (`replay.json`: `replay_only=true, physical_steps=0`) |
| KIMODO closed loop (wb_kimo_p6l1, 20/20 gates), close-up full | [g1-rightcube-sim-grasp-closeup.mp4](experiments/kimodo_closed_loop_best/wb_deliverable/g1-rightcube-sim-grasp-closeup.mp4) | render reads recorded artefacts only, no dynamics |
| same, decisive segment | [g1-rightcube-sim-grasp-decisive.mp4](experiments/kimodo_closed_loop_best/wb_deliverable/g1-rightcube-sim-grasp-decisive.mp4) (t=43.2-56.8 s) | same |

All four are visualisations of recorded runs (`mj_step = 0` renders), not recordings of a re-run;
the physics numbers live in the §4 result table with per-number sources.

## 1. What is being measured

```
 text prompt
     │
     ▼
 ┌───────────────────────┐   36-column root+joint trajectory (CSV / NPZ)
 │ motion generation      │   (KIMODO or ARDY, arm prior only - no finger channels)
 └───────────────────────┘
     │  FK + joint-limit projection  ->  *_bounded.csv
     ▼
 ┌───────────────────────┐
 │ SONIC v1.1 encoder     │  ONNX, IN this repo (50,117,796 B)
 │ + policy network       │  observation config: 57 qpos / 55 nv / 43 nu
 └───────────────────────┘
     │  body torques                ▲                │
     ▼                              │                ▼
 ┌───────────────────────────────────────────────────────────┐
 │ MuJoCo 3.2.7, 500 Hz, free-base robot, cube = free body    │
 │   fingers: geometric pinch / IK -> independent PD torque    │
 │   table top 0.757 m, no pedestal, cube 35 mm or 80 mm       │
 └───────────────────────────────────────────────────────────┘
     │  per-step contacts, pad forces, COM/COP, drift
     ▼
 ┌───────────────────────┐     ┌──────────────────────────────┐
 │ gate set (20 / 22 /    │ ──▶ │ result.json: success + gates │
 │ wholehand-v2)          │     │ + max/hold lift, slip, forces│
 └───────────────────────┘     └──────────────────────────────┘
```

A grasp counts as successful only if the cube is held by **friction on the finger pads** while the base
is free and there is no pedestal - earlier weld-based rigs were shown to lift the cube by equality
constraint without touching it, and those numbers are kept here only as history.

### 1.1 ARDY whole-hand chain, 35 mm (`cube35_wholehand_trial32`)

```
[before the run - two independent preparation lines, artefacts in repo]
  A) text prompt -> ARDY motion generation (148-dim tokens)
       -> decode -> geometric/safety repair -> profile chain (native_profile28/29/30)
  B) grasp geometry planning -> surface_exec25_plan.json
       (wrist target / waypoints / open-hand pose)

[during the run - every sim step dt=2 ms; phase state machine:
  SETTLE->RAISE->APPROACH->PRESHAPE->ALIGN->CLOSE->TEST_LIFT->LIFT->HOLD->RELEASE->FINAL]

   ARDY reference chain (profile frames + waypoints)   surface_exec25_plan.json
            |                                                 |
            v                                                 v
   wrist task IK (right arm 7) -> left mirror      MaterialHand22 geometry solve
            |                                       (against the cube pose G1 reports)
            v                                                 | <-->
   C2 full29 reference filter                          GripForce26 grip-force loop
            |                                          (measured pad forces from G1)
            v                                                 |
   +--------------------+                        +----------------------+
   | SONIC v1.1 policy  |                        | stable_hand finger PD|
   | (encoder ONNX)     |                        | gains = core.gains() |
   +---------+----------+                        +----------+-----------+
             | 29 body torques                             | right 7 + left rest
             v                                             v
   +------------------------------------------------------------+
   |       G1 + 35 mm cube (MuJoCo, nu=43)                       |
   +------------------------------------------------------------+
             ^                                            ^
             +-- qpos/qvel fed back into SONIC obs -------+
             +-- pad contact forces / cube pose fed back -+
                       | per-frame record
                       v
        gate set v6 (22 gates) -> result.json (trial32: 22/22 green)
```
So yes: ARDY -> SONIC -> G1, and G1 state -> finger PD -> G1, every sim step (a closed loop).
Source: `rep/normal_runner32.py` (writes `d.ctrl[:29]=ctrl.torques(...)`,
`d.ctrl[36:43]=stable_hand_torques(...)`, `d.ctrl[29:36]=...`; grip loop
`handgoal=force_control.update(d, measured_digit_forces)`; runtime_stamp `ardy_use`:
"Raw ARDY token148 is decoded, not passed as SONIC token64").

### 1.2 ARDY whole-hand chain, 80 mm and the 360-cell batch

```
 text prompt
     v
 ARDY motion generation -> right-arm frame prior (near_s42.npz, in repo)
     v
 +-----------------------------------------------------------+
 | reference-frame wrist IK + bounded geometry search         |
 | (wholehand_side.py: hull clearances / contact checks       |
 |  + calibration npz -> plan.json, open-hand pose)           |
 +-----------------------------------------------------------+
     | arm/body reference            | finger target = closed fit of plan
     v                               v
 +---------------------------+  +------------------------------+
 | SONIC v1.1 policy         |  | independent 7-joint finger PD|
 | all29 decode              |  | kp=40 kd=2 armature=0.1      |
 | -> ctrl[0:29] torso+arms  |  | -> ctrl[36:43] right hand    |
 +---------------------------+  | -> ctrl[29:36] left = rest   |
                                +------------------------------+
     +------------------┴------------------+
     v
 MuJoCo 3.2.7 (free base, free cube) -> wholehand-v2 gates -> result.json
```
Source: `execute_side.py` header and stamp - "SONIC all29 decoded motor targets; independent
seven-joint finger PD"; writes `d.ctrl[:29]=policy.torques(...)`, `d.ctrl[36:43]=...`.
The 80 mm single cell and the 360-cell batch **share this skeleton** (the batch grids cube size /
position / gains and changes seeds). It is **not** the same chain as 35 mm above: different reference
path (decode-repair-IK-filter vs arm-prior+wrist-IK) and different hand controller (grip-force loop
vs fixed-gain PD).

### 1.3 KIMODO arm-prior closed loop (`kimodo_closed_loop_best`)

```
 text prompt
     v
 KIMODO motion generation (Kimodo-G1 weights; text-encoder preset injected at run time)
     v
 generated fragments -> converted to harness motion inputs (*_conv.npz, same family as ARDY priors)
     v
 +-----------------------------------------------------------+
 | official SONIC S1000 grasp harness (sonic_grasp.py)       |
 |   body: policy tracks the motion input -> torso+arm       |
 |   fingers: geometric pinch re-location + IK -> finger PD  |
 +-----------------------------------------------------------+
     v
 MuJoCo 3.2.7 (free base, no pedestal, free 35 mm cube)
     v
 gate set v5 (20 gates) -> result.json (wb_kimo_p6l1: 20/20 green)
```
Source: `harness_nat2/run_cell.sh` (`N1_MOTION_STEM` defaults to `near_s42`; cells pass
`kimo_reach_s43`, `p1_conv`, ...).

## 2. Repository layout

```
.
├── README.md                     you are here
├── requirements.txt              versions recovered from artefact fields (not a lock file)
├── EXPORT-MANIFEST.tsv           authoritative per-file list: path, bytes, mtime, sha256, class
├── ASSETS-MANIFEST.tsv           every artefact that a run recorded by sha256 but that is NOT here
├── docs/
│   ├── REPRODUCTION.md           three reproduction tiers, entry points, command -> expected field
│   ├── EXPERIMENTS.md            one row per run directory, with the measurement rule
│   ├── RUN_MAP.md                new path  <->  source task-card path
│   ├── TROUBLESHOOTING.md        symptoms and minimal fixes
│   ├── EXCLUSIONS.md             what is left out and why
│   ├── ATTRIBUTION.md            who ran each experiment
│   └── THIRD_PARTY.md            upstream repositories, pinned commits, licences
├── src/
│   └── sonic_v11_runtime/        shared code imported by three runs (encoder wrapper, motion input,
│                                 Unitree G1 MJCF + ARDY runtime source, observation config, encoder ONNX)
├── experiments/
│   ├── cube35_wholehand_trial32/        35 mm, 22-gate pass
│   ├── cube80_sideways_wholehand/       80 mm sideways approach, 2.5 s hold
│   ├── batch_wholehand_360/             300 main + 60 ablation cells
│   ├── w4_transfer_arms/                nine transfer-arm variants (palm support, PD, substep, 80 mm)
│   ├── kimodo_closed_loop_best/         KIMODO prior through the official grasp harness (20/20 gates)
│   ├── kimodo_generation_matrix/        17-cell generation matrix, protocol only
│   ├── kimodo_input_gate/               evaluator + input gate that rejected those 17 cells
│   ├── kimodo_three_finger_envelope/    three-finger envelope, kinematic drive with real contact
│   ├── tripod_50mm_negative/            50 mm tripod: 0/25 negative
│   ├── tripod_iter01_91/                iteration log of the tripod line, single pass at iter91
│   ├── hand_jitter_analysis/            finger-jitter diagnostics
│   └── replay_videos_non_physical/      renders with mj_step = 0 (visualisation, not a rerun)
├── refs/
│   ├── cross_run/                         files from 7 other runs, pulled in only because an
│   │                                      artefact here records their sha256
│   └── from_shared_tree/                  8 files that existed only in the node's shared tree
└── tools/
    ├── verify_repo.py            one-command self-check (see §3)
    ├── build_export_manifest.py  regenerate EXPORT-MANIFEST.tsv
    ├── make_links.sh             recreate the lib/ symlinks git cannot carry
    ├── fetch_assets.sh           how to obtain the missing artefacts + mandatory sha check
    └── mesh_source_comparison.tsv measured comparison against the public mesh mirror
```

Inside an `experiments/<name>/` directory the layout is deliberately unchanged from the source
(`rep/`, `out/<cell>/result.json`, `raw/`, `configs/`, `lib/`) so that the paths quoted inside reports
and `runtime_stamp` fields can still be resolved by hand.

## 3. Reproduce it - three tiers, start with the first one

### Tier 1 - verify every recorded result (needs only Python 3.8+)

```bash
git clone <this repo> && cd DL-G1-Grasp
python tools/verify_repo.py
```

Expected last line `VERDICT=PASS`, plus, among others:

```
[manifest] PASS missing=0 sizediffer=0 shadiffer=0 (sha checked 400/11021 rows, mode=sample)
[headline] PASS all 14 assertions match
[batch]    planned=360 present=353 absent=['A000','B000','B051','C000','D000','NGF000','NWS000']
[batch]    PASS sha(manifest.json) == summary.manifest_sha256
[deps]     PASS every recorded-but-absent artefact has a row in ASSETS-MANIFEST.tsv
```

Add `--full` to hash all 11,021 files (~500 MB of reads).

### Tier 2 - recompute the aggregates

```bash
python3.10 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -c "import mujoco,numpy,onnxruntime;print(mujoco.__version__,numpy.__version__,onnxruntime.__version__)"
# expected: 3.2.7 1.26.4 1.23.2

bash tools/make_links.sh                 # three runs import the shared runtime via <run>/lib
python experiments/batch_wholehand_360/summarize_batch.py
```

The recomputed group counts will be **288/300 and 23/60** where the recorded summary says 292 and 25.
That difference is exactly the seven cells whose `result.json` no longer exists anywhere; there is no
other disagreement, and all 353 shared rows hash-match. The pool of 360 configurations can be
regenerated bit-for-bit with `make_trials.py` plus seeds `20261009` / `20261010` and numpy 1.26.4.

### Tier 3 - rerun the physics

Two things are not in the repo:

| Missing | Size | Where to get it |
|---|---|---|
| `model_decoder.onnx` | 149,778,638 B | published upstream: [https://huggingface.co/nvidia/GEAR-SONIC](https://huggingface.co/nvidia/GEAR-SONIC) - fetch from there and verify sha256 `34bae857...` (registered in `ASSETS-MANIFEST.tsv`) |
| the Python environment of the original runs | - | python 3.10 + mujoco 3.2.7 etc. via `requirements.txt`; the batch scheduler additionally asserts node-only conditions - use the per-cell entry instead |

The Unitree G1 meshes (60 STL, 33.3 MB) **are included** at `src/sonic_v11_runtime/src/g1/meshes/`
(50 of them sha-verified against `experiments/batch_wholehand_360/model-assets.json`). MJCF files
reference meshes by absolute source-machine paths; `python tools/fix_meshdir.py` repoints all affected
scenes at the in-repo copy and prints the before/after hashes - a repointed scene is a rerun, not a
byte-identical replay of the recorded one. With the decoder fetched and the environment installed,
the physics runs; the recorded results can already be checked without any of this (tier 1-2).

## 4. Results worth quoting, with their source

| Result | Where it comes from |
|---|---|
| 35 mm, all fingers in physics, held 84.483 mm above the lift-off point with 0.52 mm slip, 22/22 gates | `experiments/cube35_wholehand_trial32/rep/out/normal_trial32/result.json` → `hold_min_lift_m`, `hold_slip_m`, `gates`, `success` |
| 80 mm sideways, lifted 108.574 mm and held for 2.5 s | `experiments/cube80_sideways_wholehand/out/side80_native3/result.json` → `max_lift_m`, `hold_steps` |
| 360-cell batch: 292/300 main, 25/60 ablation (recorded); 353 cells verifiable here | `experiments/batch_wholehand_360/summary.json` → `main_300_total.counts`, `ablation_60_total.counts` |
| Nine transfer arms: 21 of 105 cells all-green under 20 gates | recomputed by `tools/verify_repo.py` over `experiments/w4_transfer_arms/ws4_migrate/rep_ext_*/` |
| KIMODO arm prior: one cell 20/20 gates, `max_lift_m = 0.1439862432245319`, 3/6 segments | `experiments/kimodo_closed_loop_best/harness_nat2/raw/wb_kimo_p6l1.result.json` |
| KIMODO 17-cell generation matrix: 0 cells entered the closed loop, all rejected at the input gate | `experiments/kimodo_input_gate/table_x04.csv`, `master_table_x05.csv` |

Each gate count is a different standard (20, 21, 22 and the 12/13/16/17 `wholehand-v2` groups coexist),
and MuJoCo 3.2.7 and 3.14.0 both appear - so these numbers are not one leaderboard. See
`docs/EXPERIMENTS.md` for the reading rules.

## 5. Not included, and where to get it

Model weights, vendor SDKs, virtual environments, upstream third-party sources and raw per-run
evidence are not part of this repo. Every artefact that a run references by sha256 is registered in
[`ASSETS-MANIFEST.tsv`](ASSETS-MANIFEST.tsv) with its hash, size and source location, and details are
in [docs/EXCLUSIONS.md](docs/EXCLUSIONS.md). The large jitter-evidence bundle is attached to a GitHub
Release of this repo as `hand-jitter-evidence.tar.gz` - after downloading, verify

```
sha256: 06bdefb69b1420cd0a42bb8eff2b09d30758df0c145e2810832c511490c467ea
```

## 6. Licence and attribution

This repo's own code and data are released under the [MIT License](LICENSE).
Third-party components (SONIC, KIMODO, ARDY, Unitree G1 assets, ...) keep their own terms and are
pinned in [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md); they are not redistributed here.
Experiment ownership is listed per run, with no inference or merging, in
[docs/ATTRIBUTION.md](docs/ATTRIBUTION.md).

## 7. Questions

Open an issue and paste the output of `python tools/verify_repo.py --full`.
