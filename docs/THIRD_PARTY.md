# Third-party components

Nothing upstream is vendored into this repo: we record the pinned commit and the licence, and point at the
official source. Where a licence's redistribution terms are unclear, the component stays out.

| Upstream | How it is used here | Licence (as published) | Notes |
|---|---|---|---|
| `NVlabs/GR00T-WholeBodyControl` (SONIC) | harness semantics, scene/robot structure; the policy weights come from `nvidia/GEAR-SONIC` | code Apache-2.0; weights **NVIDIA Open Model License** | the encoder committed here (`src/sonic_v11_runtime/sonic_v11/model_encoder.onnx`, 50,117,796 B) is that weight class: 100 MiB-safe, but its licence terms for redistribution are the group's call |
| `nv-tlabs/kimodo` | arm-prior generator, used through its outputs only | Apache-2.0 (code); checkpoints/data under their own HF terms | pinned `58e781898b3d...`; the node's working tree additionally carried three uncommitted edits (text encoder swapped, transition-frame count changed), so **the pin alone does not describe the code that produced these outputs** - which is why one reference cell no longer reproduces |
| `google-deepmind/mujoco_menagerie` | reference for fingertip/collision geometry and scene layout | `unitree_g1` subdir BSD-3 (copyright HangZhou YuShu / Unitree) | measured: 29 of the 50 recorded mesh hashes match the public copy, 17 differ, 4 absent - see `tools/mesh_source_comparison.tsv` |
| `Unitree` robot descriptions (as redistributed by the above) | G1 MJCF + meshes used by every run | per-upstream | the upstream projects themselves do not package robot definitions |
| ARDY (`nv-tlabs` line) | arm prior generator | **not verified** (two fetch attempts failed) | until verified, neither its source nor its weights are mirrored |
| `ARISE-Initiative/robosuite`, `google-deepmind/dm_control` | precedent only for contact parameters (friction, `solref`, `condim` values quoted in configs) | MIT / Apache-2.0 | dm_control asks for a prominent notice on modified files |
| MUSA SDK / vLLM-MUSA images | not used by any run in this repo (everything recorded here is CPU MuJoCo) | not redistributable | only the load-stage manifest is mirrored, in `refs/from_shared_tree/images/` |

Our own code and data are MIT-licensed (see `LICENSE`). Every upstream component above stays out of
this repository unless its licence clearly allows redistribution; the table records where each one lives.
