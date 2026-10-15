# What is not in this repo, and how to get it

The rule behind the mirror: keep everything that *defines* an experiment (code, configs, MJCF,
recorded inputs, machine-readable results, method write-ups); leave out everything that is a
*distributable product of someone else* (weights, vendor SDKs, virtual environments, upstream repos)
or raw per-run evidence too large or too sensitive to publish.

## Categories left out

| Class | Scale | Reason | Recovery route |
|---|---|---|---|
| Policy weights | `model_decoder.onnx` 149,778,638 B (recorded by sha 4,022 times across the batch cells) | weight class, and above GitHub's 100 MiB hard file limit | upstream `nvidia/GEAR-SONIC`, then verify sha |
| Robot mesh assets | 60 STL, 33,319,908 B; 50 of them have recorded hashes in `experiments/batch_wholehand_360/model-assets.json` | upstream model assets; not redistributed here | copy from the internal node (the only byte-exact route) |
| Per-run arrays and video | `trajectory.npz`, `dense_trace.npz` (~14 MB each), replay mp4 per cell | size; raw evidence streams are not published | rsync by cell name; verify against `ASSETS-MANIFEST.tsv` |
| Environments and vendored deps | shared venv, `pydeps/`, `uv-cache/`, site-packages | belong to other tasks; not repo content | `requirements.txt` |
| Vendor SDK / MUSA stack | `musa_rootfs` (~23 GB), probe extracts | not redistributable | vendor channels |
| Upstream sources | ARDY, KIMODO, sonic-bridge working trees | third-party code | pins and hashes in `docs/THIRD_PARTY.md` |
| Ledger material | journals, issue registry, governance rules, per-run reports | they live in the sibling ledger repo | `DL-G1-record` |

Every artefact that a run *referenced by sha256* but that is not present has exactly one row in
`ASSETS-MANIFEST.tsv`: hash, size (when known), source location, the field(s) that recorded it, how many
files refer to it, and its status. `python tools/verify_repo.py` asserts this coverage
(`[deps] ... unregistered=0`) so the registry cannot silently fall behind.

## Large evidence bundle

`hand-jitter-evidence.tar.gz`, 635,107,405 B, sha256
`06bdefb69b1420cd0a42bb8eff2b09d30758df0c145e2810832c511490c467ea`, is attached to a GitHub Release of
this repository rather than tracked in git. Verify the sha256 of whatever you download before using it.

## Security posture

A credential-pattern scan of the full file list (private-key payload, GitHub token shapes, `token=/secret=`
pairs) is green: no key material, no tokens, no private-key payloads. What the scan does report is internal
naming - account/group names, usernames, absolute paths inside the mirrored artefacts. That is acceptable
while both repos are **private**; before any flip to public a scrubbed copy must be produced, because
GitHub's push protection does not catch internal host names, usernames or SSH fingerprints.
