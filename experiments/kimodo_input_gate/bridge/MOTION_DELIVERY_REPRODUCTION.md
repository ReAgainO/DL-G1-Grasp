# Motion Integration Delivery Reproduction

Run commands from the repository root with `.venv310`.

## Fast Acceptance

Validates the scene objects and physics constraints, all four source assets,
loader provenance, baseline dimensions and pinned hashes:

```bash
.venv310/bin/python tools/accept_motion_delivery.py
```

Run unit tests:

```bash
.venv310/bin/python -m unittest discover -s tests -v
```

## Full Acceptance

Adds Kimodo and ARDY SONIC runtime smoke tests plus the physical keyframe
positive and `--no-grip` negative controls:

```bash
.venv310/bin/python tools/accept_motion_delivery.py --full
```

The Kimodo/ARDY smoke cases are integration checks. They require changing
reference windows, zero fixed-arm writes and finite execution, but do not
require grasp success because the supplied CSV files were not generated for
the current cube scene.

## Regenerate the Physical Baseline

```bash
.venv310/bin/python runners/run_grasp.py \
  --headless --quiet \
  --export-baseline-csv \
  baselines/g1_cube_grasp_v1/g1_cube_grasp_keyframe_50hz.csv \
  --export-baseline-manifest \
  baselines/g1_cube_grasp_v1/g1_cube_grasp_keyframe_50hz.manifest.json
```

The runner writes the two files only after the keyframe grasp passes all
physical acceptance thresholds. The CSV is root plus 29 body joints at 50 Hz;
the independent hand command and measured result are stored in the manifest.

Negative control:

```bash
.venv310/bin/python runners/run_grasp.py \
  --headless --quiet --no-grip --allow-failure
```

## Individual Source Smoke Tests

Kimodo:

```bash
.venv310/bin/python runners/run_grasp.py \
  --headless --quiet --allow-failure --duration 2.0 \
  --motion-source kimodo \
  --motion-file server_reports/assets/kimodo_ardy_qpos/kimodo_walk_s0.csv \
  --source-fps 50 \
  --close-start 1.1 --close-duration 0.3 \
  --lift-start 1.4 --lift-duration 0.4
```

ARDY:

```bash
.venv310/bin/python runners/run_grasp.py \
  --headless --quiet --allow-failure --duration 2.0 \
  --motion-source ardy \
  --motion-file server_reports/assets/kimodo_ardy_qpos/ardy_final_s0.csv \
  --source-fps 50 \
  --close-start 1.1 --close-duration 0.3 \
  --lift-start 1.4 --lift-duration 0.4
```

For each source, accept integration only when the output contains
`control_mode=generated-motion`, both fixed-arm counts are zero, and the
reference window changes.

## Viewer

On macOS the passive MuJoCo viewer must be launched with `mjpython`:

```bash
.venv310/bin/mjpython runners/run_grasp.py
```

Kimodo viewer:

```bash
.venv310/bin/mjpython runners/run_grasp.py \
  --allow-failure --motion-source kimodo \
  --motion-file server_reports/assets/kimodo_ardy_qpos/kimodo_walk_s0.csv \
  --source-fps 50 \
  --close-start 1.1 --close-duration 0.3 \
  --lift-start 1.4 --lift-duration 0.8
```

ARDY viewer uses the same command with:

```text
--motion-source ardy
--motion-file server_reports/assets/kimodo_ardy_qpos/ardy_final_s0.csv
```

Closing the viewer early ends the run and may produce a failed physical result;
use `--allow-failure` for inspection.

## Optional Render Evidence

```bash
MUJOCO_GL=glfw .venv310/bin/python runners/run_grasp.py \
  --offscreen --quiet \
  --out-dir renders_grasp_delivery --render-every 100
```

This writes PNG frames. Rendering is evidence for visual inspection; the
numeric physical criteria remain authoritative.
