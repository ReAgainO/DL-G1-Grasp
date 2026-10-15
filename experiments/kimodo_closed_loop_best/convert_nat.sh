#!/usr/bin/env bash
# Convert the new natural-grasp candidates into harness staging stems.
# Only the two best-scoring prompts (n2 roll=64.9, n4 roll=89.1) plus n3 as a
# control are converted, to keep the 20-gate verification budget small.
set -uo pipefail
B=/data/group4/20261008-232029-workbuddy-34e89f61
R="$B/harness_s1000/rep"
P=/data/group4/20261004-205550-qoder-1280b420/env/bin/python
export MUJOCO_GL=disable PYTHONPATH="$R" TMPDIR="$R/tmp" XDG_CACHE_HOME="$R/cache"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p "$B/kimodo_conv"
cd "$R"

for n in n2 n3 n4; do
  echo "=== convert $n ==="
  $P -B kimo2harness.py --npz "$B/reach_nat/$n.npz" \
      --stem "$B/kimodo_conv/${n}_conv" || exit 11
done

echo
echo "########## format check ##########"
$P - <<'PY'
import numpy as np, os, glob
B = "/data/group4/20261008-232029-workbuddy-34e89f61/kimodo_conv"
for p in sorted(glob.glob(B + "/n*_conv.csv")):
    a = np.loadtxt(p, delimiter=",", ndmin=2)
    stem = os.path.basename(p)
    q = a[:, 3:7]
    qn = np.linalg.norm(q, axis=1)
    print("%-14s rows=%-5d cols=%-3d nan=%d  quat_norm[min=%.6f max=%.6f]  root_uniq=%s"
          % (stem, a.shape[0], a.shape[1], int(np.isnan(a).sum()),
             qn.min(), qn.max(),
             np.unique(np.round(a[:, :3], 6), axis=0)[:1].tolist()))
PY
echo CONVERT_NAT_DONE
