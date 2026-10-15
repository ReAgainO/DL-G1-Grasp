#!/usr/bin/env python3
"""Inspect LeRobot v2.1 meta/info.json + parquet schema of episode 0."""
import json
import glob
import pandas as pd
import pyarrow.parquet as pq

BASE = "/data/group4/20261008-221515-qoder-03c4673f/ws2_dataset/raw"

print("=== meta/info.json (selected) ===")
info = json.load(open(f"{BASE}/meta/info.json"))
for k in ["codebase_version", "robot_type", "total_episodes", "total_frames", "total_tasks",
          "total_videos", "total_chunks", "chunks_size", "fps", "splits", "data_path", "video_path"]:
    if k in info:
        print(f"{k}: {info[k]}")
print("--- features ---")
for name, f in info.get("features", {}).items():
    d = f.get("shape")
    print(f"  {name}: dtype={f.get('dtype')} shape={d}")

print()
print("=== meta/tasks.jsonl ===")
for line in open(f"{BASE}/meta/tasks.jsonl"):
    print(line.strip()[:200])

print()
print("=== meta/episodes.jsonl first 2 ===")
for i, line in enumerate(open(f"{BASE}/meta/episodes.jsonl")):
    if i >= 2:
        break
    print(line.strip()[:300])

print()
f0 = f"{BASE}/data/chunk-000/episode_000000.parquet"
pf = pq.ParquetFile(f0)
print("=== parquet schema:", f0.split('/')[-1], "===")
print("num_rows:", pf.metadata.num_rows, "num_row_groups:", pf.metadata.num_row_groups)
print(pf.schema_arrow)
df = pd.read_parquet(f0)
print("shape:", df.shape)
print("columns:", list(df.columns))
for c in df.columns:
    v = df[c].iloc[0]
    try:
        import numpy as np
        if isinstance(v, np.ndarray):
            print(f"  {c}: ndarray len={len(v)} sample={np.asarray(v)[:4]}")
        else:
            print(f"  {c}: {type(v).__name__} = {str(v)[:100]}")
    except Exception as e:
        print(f"  {c}: {type(v).__name__}")
