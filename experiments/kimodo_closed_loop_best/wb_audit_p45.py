"""Audit the approach behaviour of every Kimodo reach clip.

For each clip, using posed_joints (world-frame joint positions, 34 points/frame):
  - identify the point that comes closest to the cube over the clip
  - report min distance to the cube centre and the vertical drop achieved
This tells us whether the clip actually brings the hand to the cube.

The failing clips (p4,p5) are expected to never approach the cube, which is why
the harness approach clock (bounded 0..26 s) never converges.
"""
import numpy as np
import os

D = "/data/group4/20261008-232029-workbuddy-34e89f61"
C = os.path.join(D, "kimodo_conv")
M = os.path.join(D, "harness_s1000", "rep", "src", "original_motions")
CUBE = np.array([0.267, -0.118, 0.7745])


def audit(path, label):
    z = np.load(path, allow_pickle=True)
    pj = np.asarray(z["posed_joints"], dtype=float)      # (T,34,3)
    rp = np.asarray(z["root_positions"], dtype=float)    # (T,3)
    T = pj.shape[0]
    d = np.linalg.norm(pj - CUBE[None, None, :], axis=2)  # (T,34)
    # the best (closest) point over the whole clip
    best = d.min(axis=1)                                  # (T,) closest joint per frame
    imin = int(np.argmin(best))
    jmin = int(np.argmin(d[imin]))
    txt = str(z["text"]) if "text" in z else ""
    print("%-12s T=%-3d best_joint=%2d  min_dist_to_cube=%.4f m @frame %d"
          % (label, T, jmin, best[imin], imin))
    print("             hand_height_at_closest=%.4f  root_z first/last=%.4f/%.4f"
          % (pj[imin, jmin, 2], rp[0, 2], rp[-1, 2]))
    if txt and txt.strip():
        print("             text=%r" % txt)
    return best[imin]


print("=" * 84)
print("KIMODO REACH CLIPS -- how close does the clip bring ANY joint to the cube?")
print("=" * 84)
res = {}
for n in ["p1", "p2", "p3", "p4", "p5", "p6"]:
    p = os.path.join(C, n + "_conv.npz")
    if os.path.exists(p):
        res[n] = audit(p, n + "_conv")

print()
print("=" * 84)
print("OFFICIAL reach baseline")
print("=" * 84)
p = os.path.join(M, "near_s42.npz")
if os.path.exists(p):
    z = np.load(p, allow_pickle=True)
    print("   keys:", list(z.keys()))
    if "posed_joints" in z:
        audit(p, "near_s42")

print()
print("=" * 84)
print("KIMODO LIFT CLIPS")
print("=" * 84)
for n in ["l1", "l2", "l3", "l4", "l5"]:
    p = os.path.join(C, n + "_conv.npz")
    if os.path.exists(p):
        audit(p, n + "_conv")

print()
print("=" * 84)
print("RANKING (closer = better approach)")
print("=" * 84)
for k, v in sorted(res.items(), key=lambda kv: kv[1]):
    print("   %s  min_dist=%.4f m" % (k, v))
