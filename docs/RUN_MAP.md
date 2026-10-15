# RUN MAP - new path in this repo <-> source task-card path in the byte-for-byte mirror

The source node organised every run by task-card directory name (`<date>-<time>-<tool>-<id>`).
This repo renames those directories to what the run actually is. Nothing else about the contents changed:
file bytes are identical to `DL-G1`, only paths differ. Use this table when a `result.json`, a log line
or a report quotes a path that no longer exists here.

| Source card | Here |
|---|---|
| `20261006-093203-codex-6385a841` | `src/sonic_v11_runtime` |
| `20261008-202654-codex-182c4568` | `experiments/cube35_wholehand_trial32` |
| `20261009-003148-codex-363f6327` | `experiments/cube80_sideways_wholehand` |
| `20261009-021611-codex-415484ce` | `experiments/batch_wholehand_360` |
| `20261008-221515-qoder-03c4673f` | `experiments/w4_transfer_arms` |
| `20261008-232029-workbuddy-34e89f61` | `experiments/kimodo_closed_loop_best` |
| `20261006-045000-qoder-x04kimodo` | `experiments/kimodo_generation_matrix` |
| `20261006-055934-qoder-x05eval` | `experiments/kimodo_input_gate` |
| `20261008-235856-codex-3c7f34c5` | `experiments/kimodo_three_finger_envelope` |
| `20261009-020500-codex-ardyside3` | `experiments/tripod_50mm_negative` |
| `20261009-025512-codex-f4a8c746` | `experiments/tripod_iter01_91` |
| `20261009-170228-codex-fcd727b9` | `experiments/hand_jitter_analysis` |
| `20261009-132809-qoder-9b946d7f` | `experiments/replay_videos_non_physical` |
| `xdep/<card>` (7 cards) | `refs/cross_run/<short-id>` |
| `node-repo/<sub>` | `refs/from_shared_tree/<sub>` |

Card-shaped *file* names were shortened the same way, e.g.
`20261008-232029-workbuddy-34e89f61-report.md` -> `34e89f61-report.md`.

Two consequences to keep in mind:

1. Paths written **inside** artefacts (`runtime_stamp.scene`, `meshdir`, `source_root`, log lines) still
   name the original absolute locations. They are not rewritten, because rewriting them would change
   the bytes that other hash fields refer to. Resolve them through this table.
2. Symlinks cannot be carried by git. Run `bash tools/make_links.sh` before importing the shared
   runtime from `cube80_sideways_wholehand`, `batch_wholehand_360` or `hand_jitter_analysis`.
