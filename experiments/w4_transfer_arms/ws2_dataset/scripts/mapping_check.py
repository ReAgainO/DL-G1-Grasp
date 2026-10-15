#!/usr/bin/env python3
"""WS2: empirical verification of teleop-command <-> state-slot pairing and
range-compliance of dataset hand slots against sonic-bridge Dex3-1 joint limits.

sonic-bridge g1_29dof_with_hand.xml (read-only source):
  LEFT  hand: middle_0 [-1.8326,0.191986], middle_1 [-2.0944,0], index_0 [-1.8326,0.191986],
              index_1 [-2.0944,0], thumb_0 [-1.0472,1.0472], thumb_1 [-0.724312,1.0472], thumb_2 [0,2.0944]
  RIGHT hand: middle_0 [-0.191986,1.8326], middle_1 [0,2.0944], index_0 [-0.191986,1.8326],
              index_1 [0,2.0944], thumb_0 [-1.0472,1.0472], thumb_1 [-1.0472,0.724312], thumb_2 [-2.0944,0]
"""
import json
import itertools
import numpy as np
import pandas as pd

BASE = "/data/group4/20261008-221515-qoder-03c4673f/ws2_dataset"
RAW = f"{BASE}/raw"
FPS = 50.0

LIM_L = {"middle_0": (-1.8326, 0.191986), "middle_1": (-2.0944, 0.0),
         "index_0": (-1.8326, 0.191986), "index_1": (-2.0944, 0.0),
         "thumb_0": (-1.0472, 1.0472), "thumb_1": (-0.724312, 1.0472), "thumb_2": (0.0, 2.0944)}
LIM_R = {"middle_0": (-0.191986, 1.8326), "middle_1": (0.0, 2.0944),
         "index_0": (-0.191986, 1.8326), "index_1": (0.0, 2.0944),
         "thumb_0": (-1.0472, 1.0472), "thumb_1": (-1.0472, 0.724312), "thumb_2": (-2.0944, 0.0)}

# hypothesis A (README-literal): state slots 22:29 = [thumb_0, thumb_1, thumb_2, middle_0, middle_1, index_0, index_1]
# hypothesis B (empirical):    state slots 22:29 = [middle_0, middle_1, index_0, index_1, thumb_0, thumb_1, thumb_2]
A = ["thumb_0", "thumb_1", "thumb_2", "middle_0", "middle_1", "index_0", "index_1"]
B = ["middle_0", "middle_1", "index_0", "index_1", "thumb_0", "thumb_1", "thumb_2"]

eps_meta = {e["episode_index"]: e for e in (json.loads(l) for l in open(f"{RAW}/meta/episodes.jsonl"))}

# ---- 1) range compliance over ALL 118 eps (state min/max per slot) ----
violA = {nm: 0 for nm in A}; violB = {nm: 0 for nm in B}
violA_R = {nm: 0 for nm in A}; violB_R = {nm: 0 for nm in B}
statsL = np.full((7, 2), np.nan); statsR = np.full((7, 2), np.nan)
mnL = np.full(7, np.inf); mxL = np.full(7, -np.inf); mnR = np.full(7, np.inf); mxR = np.full(7, -np.inf)

# ---- 2) cmd<->state pairing: over included eps, hold window from phase boundaries ----
pair_cost = np.zeros((7, 7))  # cost[c_idx, s_idx]
pair_n = np.zeros((7, 7))
for ei in range(0, 81):
    df = pd.read_parquet(f"{RAW}/data/chunk-000/episode_{ei:06d}.parquet")
    st = np.vstack(df["observation.state"].values)
    cmd = np.vstack(df["teleop.left_hand_joints"].values)
    H = st[:, 22:29]
    RH = st[:, 36:43]
    mnL = np.minimum(mnL, H.min(axis=0)); mxL = np.maximum(mxL, H.max(axis=0))
    mnR = np.minimum(mnR, RH.min(axis=0)); mxR = np.maximum(mxR, RH.max(axis=0))
    # pairing cost: use pickup->carry window; compare cmd vs state per frame,
    # cost = median |c_j - s_k| (rad), computed where |c_j|>0.05 to capture active commands
    pb = eps_meta[ei]["phase_boundaries_s"]
    a, b = int(pb[0] * FPS), int(pb[3] * FPS)
    c = cmd[a:b]; s = H[a:b]
    for j in range(7):
        act = np.abs(c[:, j]) > 0.05
        if act.sum() < 10:
            continue
        for k in range(7):
            diff = np.abs(c[act, j] - s[act, k])
            pair_cost[j, k] += float(np.median(diff)) * act.sum()
            pair_n[j, k] += act.sum()

cost = pair_cost / np.maximum(pair_n, 1)
print("=== cmd(j) vs state-slot(k): median |diff| over active-command frames (all eps 0-80) ===")
print("j\\k  " + "".join(f"  s{k:<7}" for k in range(7)))
for j in range(7):
    print(f"c{j}  " + "".join(f"{cost[j,k]:8.3f}  " for k in range(7)))

# best bijection minimizing total cost (brute force 5040)
best = None
for perm in itertools.permutations(range(7)):
    tot = sum(cost[j, perm[j]] for j in range(7))
    if best is None or tot < best[0]:
        best = (tot, perm)
tot, perm = best
print("\nbest bijection: cmd_j -> state_slot (list where index j gives target slot):", list(perm), " total_cost=%.3f" % tot)
print("interpretation (state slot k <- cmd j):", {f"s{k}": f"c{j}" for k, j in enumerate([perm.index(k) for k in range(7)])})
print("per-pair details:", {f"c{j}->s{perm[j]}": round(cost[j, perm[j]], 3) for j in range(7)})
second = sorted([(sum(cost[j, p[j]] for j in range(7)), p) for p in itertools.permutations(range(7))])[1]
print("2nd best:", round(second[0], 3), "best:", round(tot, 3), "-> separation factor:", round(second[0] / max(tot, 1e-9), 2))

# mapping cmd->state achieved by B-hypothesis if teleop cmd order = [t0,t1,t2,m0,m1,i0,i1]:
cmdc_A = ["thumb_0", "thumb_1", "thumb_2", "middle_0", "middle_1", "index_0", "index_1"]
expected_B = []  # for state slot k (order B), which cmd index (order cmdc_A) equals it
for nm in B:
    expected_B.append(cmdc_A.index(nm))
print("\nif teleop cmd order =", cmdc_A, "and state order =", B)
print("then expected cmd->state bijection perm =", expected_B)
print("empirical perm                            =", list(perm))
print("MATCH:", list(perm) == expected_B)

print("\n=== range compliance (all 118 eps, left hand slots 22:29) ===")
print("state slot full range (over all eps):")
for k in range(7):
    print(f"  s{k}: [{mnL[k]:+.4f}, {mxL[k]:+.4f}]")
for nm, k in zip(A, range(7)):
    lo, hi = LIM_L[nm]
    if mnL[k] < lo - 1e-6 or mxL[k] > hi + 1e-6:
        violA[nm] = 1
for nm, k in zip(B, range(7)):
    lo, hi = LIM_L[nm]
    if mnL[k] < lo - 1e-6 or mxL[k] > hi + 1e-6:
        violB[nm] = 1
print("hypothesis A (literal README thumb/middle/index): violated joints =",
      [nm for nm in A if violA[nm]], f"({sum(violA.values())}/7)")
print("hypothesis B (middle/index/thumb):               violated joints =",
      [nm for nm in B if violB[nm]], f"({sum(violB.values())}/7)")

print("\n=== range compliance right hand slots 36:43 ===")
for k in range(7):
    print(f"  s{k}: [{mnR[k]:+.4f}, {mxR[k]:+.4f}]")
for nm, k in zip(A, range(7)):
    lo, hi = LIM_R[nm]
    if mnR[k] < lo - 1e-6 or mxR[k] > hi + 1e-6:
        violA_R[nm] = 1
for nm, k in zip(B, range(7)):
    lo, hi = LIM_R[nm]
    if mnR[k] < lo - 1e-6 or mxR[k] > hi + 1e-6:
        violB_R[nm] = 1
print("hypothesis A violations:", [nm for nm in A if violA_R[nm]], f"({sum(violA_R.values())}/7)")
print("hypothesis B violations:", [nm for nm in B if violB_R[nm]], f"({sum(violB_R.values())}/7)")
