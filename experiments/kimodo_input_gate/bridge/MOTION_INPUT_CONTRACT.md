# Kimodo / ARDY Motion Input Contract

## Scope

This contract defines the file accepted by the Kimodo and ARDY loaders and the
additional metadata required to claim a scene-conditioned cube grasp.

Passing the loader and SONIC runtime checks proves integration only. A motion
generated before the current table and cube scene existed is not treated as a
grasp trajectory for that scene.

## CSV Format

The file is headerless numeric CSV with exactly 36 finite values per row:

| Columns | Meaning | Unit / convention |
|---|---|---|
| `0:3` | floating-root position `x, y, z` | metres, world frame |
| `3:7` | floating-root quaternion `w, x, y, z` | unit quaternion |
| `7:36` | 29 body joint positions | radians, MuJoCo actuator order |

The world frame is right-handed and Z-up. FPS is mandatory external metadata;
it is never inferred from row count. Quaternion order is always `wxyz`.

The 29 joint columns are:

```text
left_hip_pitch_joint
left_hip_roll_joint
left_hip_yaw_joint
left_knee_joint
left_ankle_pitch_joint
left_ankle_roll_joint
right_hip_pitch_joint
right_hip_roll_joint
right_hip_yaw_joint
right_knee_joint
right_ankle_pitch_joint
right_ankle_roll_joint
waist_yaw_joint
waist_roll_joint
waist_pitch_joint
left_shoulder_pitch_joint
left_shoulder_roll_joint
left_shoulder_yaw_joint
left_elbow_joint
left_wrist_roll_joint
left_wrist_pitch_joint
left_wrist_yaw_joint
right_shoulder_pitch_joint
right_shoulder_roll_joint
right_shoulder_yaw_joint
right_elbow_joint
right_wrist_roll_joint
right_wrist_pitch_joint
right_wrist_yaw_joint
```

The loader converts these columns to canonical IsaacLab order using the single
`M2I` / `I2M` mapping in `adapters/sonic_action_adapter.py`.

## Validation

The loader rejects:

- empty files, headers, non-numeric values, NaN or Inf;
- a row count of columns other than 36;
- missing, zero, negative or non-finite FPS;
- non-unit root quaternions;
- a joint skeleton or order different from the list above;
- joint-limit excess greater than `0.02 rad`.

Every accepted trajectory records source path, SHA-256, loader name, frame
count, FPS, model XML path/hash and any tolerated limit clipping.

## SONIC Runtime Contract

The loader output is canonical IsaacLab 29-DoF order. Runtime preparation:

1. normalizes quaternion sign and initial heading;
2. registers root position to the current robot spawn;
3. resamples to policy rate with SLERP for root rotation;
4. computes joint velocity on the target time axis;
5. emits a 10-frame, step-5 reference window.

Each SONIC reference is 640 values:

```text
290 joint velocities + 290 absolute joint positions + 60 anchor orientation
```

Generated-motion mode must report:

```text
control_mode=generated-motion
fixed_arm_override_count=0
fixed_arm_pd_write_count=0
reference_window_count>0
reference_window_change_count>0   # for a non-static input
```

Hand joints are not present in the 36-column CSV. The seven right-hand joints
remain an independent PD controller and require explicit open/close timing.

## Scene-Conditioned Grasp Declaration

A trajectory may be labelled as a grasp for the current scene only when its
manifest also pins:

- source CSV SHA-256 and FPS;
- `g1/scene_grasp_hand.xml` SHA-256;
- `g1/g1_29dof_with_hand.xml` SHA-256;
- table centre/size and cube initial centre/size;
- right-hand open/closed targets and close/lift timing;
- `scene_conditioned=true`;
- whether success was measured under keyframe control or SONIC closed-loop
  replay.

Physical success requires all of:

```text
max_contact_bodies >= 2
lifted_height >= 0.07 m
final_clearance >= 0.04 m
lift_contact_time >= 0.25 s
```

The cube must have a free joint. Weld, adhesion, direct cube pose writes and
equivalent attachment mechanisms are prohibited.

## Delivered Baseline

`baselines/g1_cube_grasp_v1/g1_cube_grasp_keyframe_50hz.csv` is recorded from
the successful physical keyframe controller in the pinned scene. Its manifest
contains the hand timing and measured acceptance metrics.

It is a ground-truth body/root reference and a reproducible physical grasp
baseline. It does not claim that SONIC closed-loop replay of that CSV has
already reproduced the grasp; the manifest keeps
`sonic_closed_loop_replay_validated=false` until that separate test passes.
