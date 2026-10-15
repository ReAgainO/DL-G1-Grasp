"""Check the converted natural-grasp candidates for OOD crouching.

wb_gen_fix.py documents that the text-encoder regression produced out-of-
distribution crouching: pelvis height 0.40-0.50 m instead of 0.73-0.79 m.
n2_conv.csv shows a root z of 0.4463 which is exactly in that bad band, so this
must be checked before n2 is allowed anywhere near the harness.
"""
import numpy as np
import os
import glob

B = "/data/group4/20261008-232029-workbuddy-34e89f61"
CONV = os.path.join(B, "kimodo_conv")
NAT = os.path.join(B, "reach_nat")

print("=" * 96)
print("ROOT HEIGHT / CROUCH CHECK -- converted clips (36-col CSV)")
print("=" * 96)
print("%-16s %-10s %-12s %-12s %s" % ("clip", "rows", "root_z_min", "root_z_max", "verdict"))
print("-" * 96)
BAD_LO, BAD_HI = 0.40, 0.55          # the documented OOD crouch band
for p in sorted(glob.glob(CONV + "/n*_conv.csv")):
    a = np.loadtxt(p, delimiter=",", ndmin=2)
    z = a[:, 2]
    lo, hi = z.min(), z.max()
    verdict = "OOD-CROUCH" if hi < 0.60 else ("ok" if 0.70 <= hi <= 0.85 else "check")
    print("%-16s %-10d %-12.4f %-12.4f %s" % (os.path.basename(p), a.shape[0],
                                              lo, hi, verdict))

print()
print("=" * 96)
print("REFERENCE -- accepted + baseline clips")
print("=" * 96)
for name in ["p6_conv", "p3_conv", "l1_conv"]:
    p = os.path.join(CONV, name + ".csv")
    if os.path.exists(p):
        a = np.loadtxt(p, delimiter=",", ndmin=2)
        print("%-16s %-10d %-12.4f %-12.4f" % (name, a.shape[0], a[:, 2].min(), a[:, 2].max()))
p = os.path.join(B, "harness_s1000", "rep", "src", "original_motions", "near_s42.csv")
if os.path.exists(p):
    a = np.loadtxt(p, delimiter=",", ndmin=2)
    print("%-16s %-10d %-12.4f %-12.4f  (official baseline)" %
          ("near_s42", a.shape[0], a[:, 2].min(), a[:, 2].max()))

# also compare the RAW kimodo output root before conversion, to see whether the
# crouch is native to the generated motion or introduced by kimo2harness
print()
print("=" * 96)
print("RAW Kimodo npz root height (before conversion) + pelvis proxy")
print("=" * 96)
for n in ["n1", "n2", "n3", "n4", "n5", "n6"]:
    p = os.path.join(NAT, n + ".npz")
    if not os.path.exists(p):
        continue
    z = np.load(p, allow_pickle=True)
    rp = np.asarray(z["root_positions"], float)
    pj = np.asarray(z["posed_joints"], float)
    # pelvis is usually point 0 or 1; report the lowest torso point instead
    print("%-4s root_z[min=%.4f max=%.4f]  joints_z_min=%.4f (lowest body point)" %
          (n, rp[:, 2].min(), rp[:, 2].max(), pj[:, :, 2].min()))
