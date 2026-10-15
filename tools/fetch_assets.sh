#!/usr/bin/env bash
# fetch_assets.sh — how to obtain the artefacts that a physics rerun requires but this repo does not carry,
# and the mandatory byte check after you obtain them. This script itself only verifies; it never downloads.
#
# What is missing and why
#   model_decoder.onnx   149,778,638 B   weight + above GitHub's 100 MiB per-file limit
#   per-run arrays/video trajectory.npz, dense_trace.npz (~14 MB each), replay mp4
#     (only needed to re-derive per-frame gate criteria of a recorded run; a rerun makes its own)
# The Unitree G1 meshes are NOW IN THIS REPO (src/sonic_v11_runtime/src/g1/meshes).
# Everything else is listed row by row in ASSETS-MANIFEST.tsv (sha256 / bytes / source path /
# which field recorded it / how many times).
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f ASSETS-MANIFEST.tsv ] || { echo "ASSETS-MANIFEST.tsv missing - pull first"; exit 2; }

# Route A (the only route that matches every byte): copy from the internal node, e.g.
#   rsync -a --progress <NODE>:/<run-root>/src/sonic_v11_runtime/g1/meshes/ src/sonic_v11_runtime/g1/meshes/
#   rsync -a --progress <NODE>:/<run-root>/src/sonic_v11_runtime/sonic_v11/model_decoder.onnx \
#           src/sonic_v11_runtime/sonic_v11/
# Host names and credentials are intentionally not stored in this repo.
#
# Route B (public mirror, known to be partial): see tools/mesh_source_comparison.tsv
#   measured against the 50 mesh hashes recorded in experiments/batch_wholehand_360/model-assets.json:
#   MATCH 29 / DIFFER 17 / NOT PRESENT 4. The differing files are the hand and head collision meshes,
#   i.e. exactly the geometry that carries contact - a substituted mesh changes the physics. Do not use them.
#
# Route C (GitHub Release assets, e.g. the 635 MB jitter bundle): a deploy key cannot fetch release
#   assets (Git protocol only); use a token with Contents:read:
#   curl -sSL --fail --retry 3 -H "Authorization: Bearer ${GH_TOKEN}" -H "Accept: application/octet-stream" \
#        "https://api.github.com/repos/<OWNER>/<REPO>/releases/assets/<ASSET_ID>" -o hand-jitter-evidence.tar.gz

python3 - <<'PY'
import hashlib, os
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda: f.read(1<<20), b''): h.update(b)
    return h.hexdigest()
present={}
for dp,dns,fns in os.walk('.'):
    if '.git' in dp: continue
    for fn in fns:
        p=os.path.relpath(os.path.join(dp,fn),'.').replace(os.sep,'/')
        if p=='ASSETS-MANIFEST.tsv': continue
        present[sha(p)]=p
rows=[l.rstrip('\n').split('\t') for l in open('ASSETS-MANIFEST.tsv',encoding='utf-8') if l.strip()]
if rows and rows[0][0]=='sha256': rows=rows[1:]
have=sum(1 for r in rows if r[0] in present)
print('registered artefacts=%d  already present locally=%d  still missing=%d'%(len(rows),have,len(rows)-have))
for r in rows:
    if r[0] in present:
        print('  OK   %s..  %s'%(r[0][:12], present[r[0]]))
PY
echo
echo "Mesh-specific check (recommended instead of eyeballing):"
echo "  python tools/verify_repo.py --meshes src/sonic_v11_runtime/g1/meshes"
