"""Quantify wrist/forearm twist in the existing Kimodo reach clips.

The complaint is that the delivered motion "twists the arm" to grasp. We need an
objective number before and after, otherwise "more natural" is not measurable.

Method
------
posed_joints gives world-frame joint positions (T, 34, 3). The right-arm chain in
this skeleton ends at point 33 (the hand). We take the hand-forward chain
(points around wrist/elbow/shoulder) and measure:

  1. the wrist-to-elbow direction vs the elbow-to-shoulder direction:
     the bend angle at the elbow. A very small (near-straight) or oddly bent
     elbow is a symptom of an unnatural pose.
  2. the vertical orientation of the palm axis (hand minus wrist), i.e. whether
     the hand points down toward the table or is rotated sideways/up.
  3. the frame-to-frame roll of the hand segment around the forearm axis,
     integrated over the clip: this is the actual "twisting" the user sees.

All quantities are reported in degrees.
"""
import numpy as np
import os
import glob

D = "/data/group4/20261008-232029-workbuddy-34e89f61"
C = os.path.join(D, "kimodo_conv")


def unit(v, eps=1e-12):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, eps)


def angle_between(a, b):
    a = unit(a); b = unit(b)
    c = np.clip((a * b).sum(-1), -1.0, 1.0)
    return np.degrees(np.arccos(c))


def describe(path, label):
    z = np.load(path, allow_pickle=True)
    pj = np.asarray(z["posed_joints"], float)      # (T,34,3)
    T = pj.shape[0]
    hand = pj[:, 33, :]
    wrist = pj[:, 32, :]
    elbow = pj[:, 31, :]
    shoulder = pj[:, 30, :]

    # elbow bend
    v1 = wrist - elbow
    v2 = shoulder - elbow
    bend = angle_between(v1, v2)

    # hand pointing direction: downward is natural for a table grasp
    hd = hand - wrist
    hd_u = unit(hd)
    # angle from straight down (0,0,-1)
    down = np.array([0.0, 0.0, -1.0])
    ang_down = np.degrees(np.arccos(np.clip((hd_u * down).sum(-1), -1, 1)))

    # twist: roll of the hand segment around the forearm axis, frame to frame
    fa = unit(wrist - elbow)
    # build a frame on the hand segment
    ref = np.array([0.0, 0.0, 1.0])
    def roll(fa_vec, hd_vec, ref_vec):
        n = unit(np.cross(fa_vec, ref_vec))
        b = unit(np.cross(fa_vec, n))
        return np.arctan2((hd_vec * b).sum(-1), (hd_vec * n).sum(-1))
    r = roll(fa, hd_u, ref)
    unwind = np.degrees(np.abs(np.diff(np.unwrap(r)))).sum()

    print("%-10s T=%-3d elbow_bend mean=%6.2f  min=%6.2f max=%6.2f | "
          "hand_vs_down mean=%6.2f | total_roll=%.2f deg"
          % (label, T, bend.mean(), bend.min(), bend.max(),
             ang_down.mean(), unwind))
    return dict(label=label, elbow_bend_mean=float(bend.mean()),
                hand_vs_down_mean=float(ang_down.mean()),
                total_roll=float(unwind))


print("=" * 118)
print("RIGHT-ARM NATURALNESS METRICS FOR THE EXISTING KIMODO REACH CLIPS")
print("=" * 118)
res = []
for n in ["p1", "p2", "p3", "p4", "p5", "p6"]:
    p = os.path.join(C, n + "_conv.npz")
    if os.path.exists(p):
        res.append(describe(p, n))

print()
print("--- reference: the OFFICIAL baseline clip ---")
M = os.path.join(D, "harness_s1000", "rep", "src", "original_motions")
for cand in ["near_s42.npz"]:
    p = os.path.join(M, cand)
    if os.path.exists(p):
        z = np.load(p, allow_pickle=True)
        print("   %s keys=%s" % (cand, list(z.keys())))
        describe(p, cand.replace(".npz", ""))

print()
print("=" * 118)
print("RANKING by total hand roll (LOWER = less twisting)")
print("=" * 118)
for r in sorted(res, key=lambda x: x["total_roll"]):
    print("   %-4s total_roll=%8.2f deg   elbow_bend_mean=%6.2f   hand_vs_down=%6.2f"
          % (r["label"], r["total_roll"], r["elbow_bend_mean"], r["hand_vs_down_mean"]))
