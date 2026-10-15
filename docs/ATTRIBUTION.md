# Attribution

Ownership is copied verbatim from each run's claim card (`claims/<task>/card.txt`, field `owner`) on the
source node. Nothing is inferred and nothing is merged: one person may open several cards with different
tools, and the tool name is part of the recorded identity.

| Here | Recorded owner | What this repo takes from it |
|---|---|---|
| `experiments/cube35_wholehand_trial32` | `codex(ReAgain0)` | 35 mm whole-hand scripts, per-trial results, findings, frozen manifest |
| `experiments/cube80_sideways_wholehand` | `codex(hp)` | 80 mm sideways baseline results, repeat/verification hashes |
| `experiments/batch_wholehand_360` | `codex(hp)` | 300 + 60 cell configs, plans, results, gate definition |
| `experiments/tripod_50mm_negative` | `codex(ReAgain0)` | 50 mm tripod negative, replay script |
| `experiments/tripod_iter01_91` | `codex(ReAgain0)` | iterations 01-91 summaries and logs (card not closed on the node) |
| `experiments/kimodo_three_finger_envelope` | `codex(ReAgain0)` | three-finger envelope sweeps |
| `experiments/hand_jitter_analysis` | `codex(hp)` | jitter diagnostics, result tables (635 MB evidence bundle not included) |
| `experiments/replay_videos_non_physical` | `qoder(ReAgain0)` | zero-physics replay renders, flagged as such |
| `experiments/w4_transfer_arms` | `qoder(ReAgain0)` | nine transfer arms, method notes, independent review artefacts |
| `experiments/kimodo_closed_loop_best` | `workbuddy(25934)` | full KIMODO closed-loop chain: harness trees, scene, runner, results, deliverable README |
| `experiments/kimodo_generation_matrix` | `qoder(ReAgain0)` | 17-cell generation protocol and manifest |
| `experiments/kimodo_input_gate` | `qoder(ReAgain0)` | evaluator, input gate, verdict tables |
| `src/sonic_v11_runtime` | `codex(hp)` (session family, confirmed against the ledger) | runtime modules the three runs import |

Three cards belong to other group members (`codex(hp)` x3, `workbuddy(25934)` x1). The mirroring action was
announced with a per-card notice describing exactly what was and was not taken and how to object; anyone
asking for removal should cite the path as listed in `EXPORT-MANIFEST.tsv`, and the response is an
append-only note plus a re-export - published history is never rewritten.

This repo is licensed under the MIT License (see `LICENSE` at the repository root). Third-party
components keep their own terms - see `docs/THIRD_PARTY.md`.
