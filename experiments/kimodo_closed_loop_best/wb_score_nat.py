"""Score the new natural-grasp prompt candidates with the same metrics used on
the old clips, so the comparison is apples-to-apples.

Metrics (degrees):
  elbow_bend      : angle at the elbow (180 = straight arm; 120-150 = natural)
  hand_vs_down    : angle of the hand axis from straight down
                    (0 = palm/hand pointing at the table = natural for a grasp)
  total_roll      : integrated frame-to-frame hand roll = the visible "twist"

Reference points measured earlier on the delivered material:
  p6 (delivered reach) : roll=118.30  hand_vs_down=125.47  elbow=173.89
  official near_s42    : roll= 79.66  hand_vs_down=161.32  elbow=169.10
Lower roll is better; hand_vs_down closer to 180 also means the hand axis points
downward (note: the metric is the angle from (0,0,-1), so ~180 deg = pointing UP,
 ~0 = pointing DOWN -- we report both interpretations).

IMPORTANT: the sign convention of the metric is "angle between the hand vector
and straight-down". A natural table grasp wants the hand vector pointing DOWN,
i.e. this angle near 0. We therefore report `hand_down_angle` where 0 is ideal.
"""
import numpy as np
import os

B = "/data/group4/20261008-232029-workbuddy-34e89f61"
NEW = os.path.join(B, "reach_nat")
OLD = os.path.join(B, "kimodo_conv")
M = os.path.join(B, "harness_s1000", "rep", "src", "original_motions")


def unit(v, eps=1e-12):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), eps)


def ang(a, b):
    a = unit(a); b = unit(b)
    return np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1)))


def metrics(path):
    z = np.load(path, allow_pickle=True)
    pj = np.asarray(z["posed_joints"], float)
    T = pj.shape[0]
    hand, wrist, elbow, shoulder = pj[:, 33], pj[:, 32], pj[:, 31], pj[:, 30]

    bend = ang(wrist - elbow, shoulder - elbow)

    hd = unit(hand - wrist)
    down = np.array([0.0, 0.0, -1.0])
    hand_down = ang(hd, down)          # 0 = pointing straight down (ideal)

    fa = unit(wrist - elbow)
    ref = np.array([0.0, 0.0, 1.0])
    n = unit(np.cross(fa, ref))
    b = unit(np.cross(fa, n))
    r = np.arctan2((hd * b).sum(-1), (hd * n).sum(-1))
    roll = np.degrees(np.abs(np.diff(np.unwrap(r)))).sum()

    return dict(T=T, elbow=bend.mean(), hand_down=hand_down.mean(), roll=roll)


rows = []
print("=" * 108)
print("NEW NATURAL-GRASP PROMPT CANDIDATES (reach_nat/)")
print("=" * 108)
print("%-6s %-5s %-14s %-16s %-12s" % ("clip", "T", "elbow_bend", "hand_down(0=best)", "total_roll"))
print("-" * 108)
for n in ["n1", "n2", "n3", "n4", "n5", "n6"]:
    p = os.path.join(NEW, n + ".npz")
    if os.path.exists(p):
        m = metrics(p)
        rows.append((n, m))
        print("%-6s %-5d %-14.2f %-16.2f %-12.2f" %
              (n, m["T"], m["elbow"], m["hand_down"], m["roll"]))

print()
print("=" * 108)
print("REFERENCE: OLD CLIPS + OFFICIAL BASELINE")
print("=" * 108)
refs = []
for n in ["p1", "p2", "p3", "p4", "p5", "p6"]:
    p = os.path.join(OLD, n + "_conv.npz")
    if os.path.exists(p):
        m = metrics(p)
        refs.append((n + "_conv(old)", m))
p = os.path.join(M, "near_s42.npz")
if os.path.exists(p):
    refs.append(("near_s42(official)", metrics(p)))
for name, m in refs:
    print("%-20s %-5d %-14.2f %-16.2f %-12.2f" %
          (name, m["T"], m["elbow"], m["hand_down"], m["roll"]))

print()
print("=" * 108)
print("RANKING of new candidates (lower roll = less twist; lower hand_down = palm nearer the table)")
print("=" * 108)
for n, m in sorted(rows, key=lambda kv: (kv[1]["roll"])):
    print("   %-4s roll=%8.2f  hand_down=%7.2f  elbow=%7.2f" %
          (n, m["roll"], m["hand_down"], m["elbow"]))
