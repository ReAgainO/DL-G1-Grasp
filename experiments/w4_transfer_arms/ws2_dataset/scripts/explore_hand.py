#!/usr/bin/env python3
"""Explore left-hand joint trajectories to determine closure direction & grasp timing."""
import json
import numpy as np
import pandas as pd

BASE = "/data/group4/20261008-221515-qoder-03c4673f/ws2_dataset/raw"
FPS = 50.0

# --- full episodes.jsonl overview ---
eps = [json.loads(l) for l in open(f"{BASE}/meta/episodes.jsonl")]
print("total episodes in meta:", len(eps))
print("fields:", list(eps[0].keys()))
has_pb = sum(1 for e in eps if "phase_boundaries_s" in e)
print("episodes with phase_boundaries_s:", has_pb)
lens = [e["length"] for e in eps]
print("length min/median/max: %d / %d / %d frames" % (min(lens), sorted(lens)[len(lens)//2], max(lens)))
print("sum frames:", sum(lens))
print("phase 1 (pickup) windows, ep0-4 & 81-83:")
for e in eps:
    if e["episode_index"] in (0, 1, 2, 3, 4, 81, 82, 83):
        print("  ep%03d len=%d pb=%s" % (e["episode_index"], e["length"], e.get("phase_boundaries_s")))

# --- episode 0 trajectories ---
df = pd.read_parquet(f"{BASE}/data/chunk-000/episode_000000.parquet")
state = np.vstack(df["observation.state"].values)
lcmd = np.vstack(df["teleop.left_hand_joints"].values)
n = len(state)
print("\n=== ep0 state shape:", state.shape, " teleop.left_hand shape:", lcmd.shape)
LH = state[:, 22:29]
RH = state[:, 36:43]
print("LH (state 22:29) per-joint min / max:")
for j in range(7):
    print("  j%d: min=%+.4f max=%+.4f" % (j, LH[:, j].min(), LH[:, j].max()))
print("RH (state 36:43) per-joint min / max:")
for j in range(7):
    print("  j%d: min=%+.4f max=%+.4f" % (j, RH[:, j].min(), RH[:, j].max()))
print("teleop.left_hand_joints min/max:")
for j in range(7):
    print("  j%d: min=%+.4f max=%+.4f" % (j, lcmd[:, j].min(), lcmd[:, j].max()))

# per-second samples of LH state, teleop cmd, eef left wrist z
eef = np.vstack(df["observation.eef_state"].values)
print("\nsec | " + " ".join("LH%d    " % j for j in range(7)) + "| " + " ".join("cmd%d   " % j for j in range(7)) + "| Lwrist xyz")
for t in range(0, int(n / FPS) + 1):
    i = min(int(t * FPS), n - 1)
    print("%3d | " % t + " ".join("%+.3f" % LH[i, j] for j in range(7)) + "| " + " ".join("%+.3f" % lcmd[i, j] for j in range(7)) + "| " + " ".join("%+.3f" % v for v in eef[i, 0:3]))
