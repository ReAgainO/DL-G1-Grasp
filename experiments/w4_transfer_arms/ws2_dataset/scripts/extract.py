#!/usr/bin/env python3
"""WS2: Extract successful-grasp left-hand configurations from mncai/G1_Dex3_Trash_LocoManipulation.

Method
------
- Per episode, left hand state H(t) = observation.state[:, 22:29] (7 dims), fps=50.
- Open reference O = per-joint median of H over [pb0-2s, pb0] (late walk phase, hand at rest).
  (pb0 = first phase boundary from meta/episodes.jsonl = start of "pick up".)
- Openness d(t) = ||H(t) - O||_2.
- d_hi = 95th percentile of d over [pb0, pb3] (pickup start .. carry end) -> closed threshold 0.8*d_hi.
- Find all contiguous "closed" runs (d > 0.8*d_hi), duration >= 2 s; the grasp hold = longest run.
- close_onset = last frame before hold where d < 0.15*d_hi (still open).
- close_complete = first frame in hold where d >= 0.9 * median(d over hold).
- cs_duration = (close_complete - close_onset)/fps seconds.
- Grasp config = per-joint H at close_complete ('cfg_complete') and median over hold ('cfg_hold').

Outputs: grasp_configs.csv (all 118 eps, excluded flag for 81-117), grasp_summary.csv (prior stats over 0-80).
"""
import json
import sys
import numpy as np
import pandas as pd

BASE = "/data/group4/20261008-221515-qoder-03c4673f/ws2_dataset"
RAW = f"{BASE}/raw"
OUT_CSV = f"{BASE}/grasp_configs.csv"
OUT_SUM = f"{BASE}/grasp_summary.csv"
FPS = 50.0
LH_SLICE = slice(22, 29)
# state slot order for each hand, empirically established (see FINDING.md):
SLOT_NAMES = ["middle_0", "middle_1", "index_0", "index_1", "thumb_0", "thumb_1", "thumb_2"]

mode = sys.argv[1] if len(sys.argv) > 1 else "test"
eps_meta = {e["episode_index"]: e for e in (json.loads(l) for l in open(f"{RAW}/meta/episodes.jsonl"))}
todo = [0] if mode == "test" else list(range(118))

rows = []
for ei in todo:
    em = eps_meta[ei]
    pb = em["phase_boundaries_s"]
    n_exp = em["length"]
    df = pd.read_parquet(f"{RAW}/data/chunk-000/episode_{ei:06d}.parquet")
    st = np.vstack(df["observation.state"].values)
    cmd = np.vstack(df["teleop.left_hand_joints"].values)
    H = st[:, LH_SLICE]
    n = len(H)
    assert n == n_exp, f"ep{ei} length mismatch {n} vs meta {n_exp}"

    # open reference: 2 s before pickup start
    a = max(int((pb[0] - 2.0) * FPS), 0)
    b = int(pb[0] * FPS)
    O = np.median(H[a:b], axis=0)
    d = np.linalg.norm(H - O, axis=1)

    i0, i3 = int(pb[0] * FPS), int(pb[3] * FPS)
    d_hi = np.percentile(d[i0:i3], 95)
    thr = 0.8 * d_hi

    closed = d > thr
    # find contiguous runs >= 2s
    runs = []
    s = None
    for i, c in enumerate(closed):
        if c and s is None:
            s = i
        elif not c and s is not None:
            if i - s >= 100:
                runs.append((s, i - 1))
            s = None
    if s is not None and n - s >= 100:
        runs.append((s, n - 1))
    runs.sort(key=lambda r: r[1] - r[0], reverse=True)

    row = dict(episode=ei, excluded=(1 if ei >= 81 else 0), n_frames=n,
               pb0_s=pb[0], pb1_s=pb[1], pb3_s=pb[3],
               n_closed_runs=len(runs),
               d_open_ref_norm=round(float(np.linalg.norm(O)), 4))
    if not runs:
        row.update(status="NO_HOLD", hold_start=None, hold_end=None, close_onset=None,
                   close_complete=None, close_duration_s=None, hold_len_s=None,
                   d_hi=round(float(d_hi), 3))
        for nm in SLOT_NAMES:
            row[f"cfg_complete_{nm}"] = None
            row[f"cfg_hold_med_{nm}"] = None
            row[f"cfg_hold_final_{nm}"] = None
        rows.append(row)
        if mode == "test":
            print(json.dumps(row, ensure_ascii=False, indent=1))
        continue

    hs, he = runs[0]
    d_hold = np.median(d[hs:he + 1])
    # onset: last frame before hold with d < 0.15*d_hi
    pre = np.where(d[:hs] < 0.15 * d_hi)[0]
    onset = int(pre[-1]) if len(pre) else max(hs - 1, 0)
    # complete: first frame in hold with d >= 0.9*d_hold
    over = np.where(d[hs:he + 1] >= 0.9 * d_hold)[0]
    comp = int(hs + over[0]) if len(over) else hs
    cfg_c = H[comp].copy()
    cfg_h = np.median(H[hs:he + 1], axis=0)
    cfg_f = np.median(H[max(he - 99, hs):he + 1], axis=0)  # last 2 s of hold = settled config
    row.update(status="OK", hold_start=hs, hold_end=he,
               close_onset=onset, close_complete=comp,
               close_duration_s=round((comp - onset) / FPS, 3),
               hold_len_s=round((he - hs) / FPS, 3),
               d_hi=round(float(d_hi), 3), d_hold=round(float(d_hold), 3),
               onset_before_pb0_s=round(pb[0] - onset / FPS, 3),
               complete_rel_pb1_s=round(comp / FPS - pb[1], 3))
    for j, nm in enumerate(SLOT_NAMES):
        row[f"cfg_complete_{nm}"] = round(float(cfg_c[j]), 4)
        row[f"cfg_hold_med_{nm}"] = round(float(cfg_h[j]), 4)
        row[f"cfg_hold_final_{nm}"] = round(float(cfg_f[j]), 4)
    rows.append(row)

    if mode == "test":
        print(f"ep{ei}: status=OK runs={len(runs)} hold=[{hs},{he}] ({(he-hs)/FPS:.2f}s) "
              f"onset={onset} complete={comp} close_duration={(comp-onset)/FPS:.3f}s d_hi={d_hi:.2f} d_hold={d_hold:.2f}")
        print("  cfg@complete:", dict(zip(SLOT_NAMES, np.round(cfg_c, 4))))
        print("  cfg_hold_med:", dict(zip(SLOT_NAMES, np.round(cfg_h, 4))))
        print("  cmd@complete:", cmd[comp])
        print("  all runs:", [(r[0], r[1], round((r[1]-r[0])/FPS, 2)) for r in runs])

if mode == "test":
    sys.exit(0)

df_out = pd.DataFrame(rows)
df_out.to_csv(OUT_CSV, index=False)
print(f"wrote {OUT_CSV} rows={len(df_out)} status_counts={df_out['status'].value_counts().to_dict()}")

# ---- summary prior over included eps (0-80) ----
inc = df_out[(df_out["excluded"] == 0) & (df_out["status"] == "OK")]
print(f"included OK episodes: {len(inc)}/81")
summ = []
for nm in SLOT_NAMES:
    for kind in ["cfg_complete", "cfg_hold_med", "cfg_hold_final"]:
        v = inc[f"{kind}_{nm}"].astype(float)
        summ.append(dict(joint=nm, value=f"{kind}", n=len(v),
                         min=round(v.min(), 4), p25=round(v.quantile(.25), 4),
                         median=round(v.median(), 4), p75=round(v.quantile(.75), 4),
                         mean=round(v.mean(), 4), max=round(v.max(), 4), std=round(v.std(), 4)))
sm = pd.DataFrame(summ)
sm.to_csv(OUT_SUM, index=False)
print(f"wrote {OUT_SUM}")
print("\n=== module-wide stats (included 0-80) ===")
for kind in ["cfg_complete", "cfg_hold_med", "cfg_hold_final"]:
    print(f"--- {kind} ---")
    print(sm[sm['value'] == kind].to_string(index=False))
print("close_duration_s stats:", inc["close_duration_s"].describe()[["min", "25%", "50%", "75%", "max"]].round(3).to_dict())
print("hold_len_s stats:", inc["hold_len_s"].describe()[["min", "25%", "50%", "75%", "max"]].round(3).to_dict())
print("onset_before_pb0_s (onset must be after pick-up start; positive = in pickup phase):",
      inc["onset_before_pb0_s"].describe()[["min", "50%", "max"]].round(3).to_dict())
print("complete_rel_pb1_s (relative to pickup end):", inc["complete_rel_pb1_s"].describe()[["min", "50%", "max"]].round(3).to_dict())
print("n_closed_runs distribution:", df_out[df_out['excluded'] == 0]['n_closed_runs'].value_counts().to_dict())
print("excluded(81-117) status:", df_out[df_out['excluded'] == 1]['status'].value_counts().to_dict())
