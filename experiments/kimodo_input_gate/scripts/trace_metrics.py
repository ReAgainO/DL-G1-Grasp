#!/usr/bin/env python3
# Turn a --trace-csv dump into the protocol section 2 metric set.
import argparse
import csv
import json
import math
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--policy-hz", type=float, default=50.0)
    ap.add_argument("--cube-mass-kg", type=float, default=0.020)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.trace)))
    f = lambda k: [float(r[k]) for r in rows]
    t = f("time_s")
    lift = f("cube_z_rel_initial")
    gap_c = f("gap_grasp_center_to_cube_m")
    d_thumb = f("dist_thumb_fingertip_m")
    d_index = f("dist_index_fingertip_m")
    d_middle = f("dist_middle_fingertip_m")
    ncb = f("n_contact_bodies_now")
    fsum = f("force_normal_sum_N")
    rootz = f("root_z_m")
    upz = f("up_z")
    trk = f("track_rms_rad")
    phases = [r["phase"] for r in rows]
    step = 1.0 / a.policy_hz
    dur = t[-1] - t[0] + step

    # lift_sustained: min over the trailing 1.0 s window (50 samples at 50 Hz)
    n1 = int(round(1.0 / step))
    tail = lift[-n1:] if len(lift) >= n1 else lift
    lift_sustained_tail1s = min(tail)
    # longest trailing contiguous window with min >= 0.05 m
    best_len, best_min = 0.0, None
    for i in range(len(lift)):
        j = len(lift)
        seg = lift[i:j]
        if seg and min(seg) >= 0.05:
            if (j - i) * step > best_len:
                best_len = (j - i) * step
                best_min = min(seg)
    # contact/force during the grasp window (phase in lift/hold/close)
    grasp_idx = [i for i, p in enumerate(phases) if p in ("lift", "hold", "close", "grasp")]
    max_cb = max(ncb)
    max_fn = max(fsum)
    fn_grasp = max([fsum[i] for i in grasp_idx], default=0.0)
    # trigger frame: first sample with >=2 contacting bodies, else gap_min frame
    trig = next((i for i, v in enumerate(ncb) if v >= 2), None)
    if trig is None:
        trig = min(range(len(gap_c)), key=lambda i: gap_c[i])
    # fell: was lifted >= 0.05 at some point and ends below 0.02
    ever = max(lift) >= 0.05
    fell = bool(ever and lift[-1] < 0.02)
    track_vals = [v for v in trk if not math.isnan(v)]
    out = {
        "trace": str(Path(a.trace).resolve()),
        "samples": len(rows),
        "episode_seconds": round(dur, 4),
        "phase_first_seen": {p: round(t[i], 3) for i, p in enumerate(phases) if p not in ()},
        "gap_min_m": round(min(gap_c), 6),
        "gap_min_fingertip_m": round(min(min(d_thumb), min(d_index), min(d_middle)), 6),
        "gap_at_trigger_m": round(gap_c[trig], 6),
        "trigger_time_s": round(t[trig], 3),
        "lift_max_m": round(max(lift), 6),
        "lift_sustained_tail1s_min_m": round(lift_sustained_tail1s, 6),
        "lift_sustained_ge5cm_trailing_seconds": round(best_len, 3),
        "lift_sustained_ge5cm_trailing_min_m": (round(best_min, 6) if best_min is not None else None),
        "n_contact_bodies": int(max_cb),
        "force_normal_N": round(max_fn, 6),
        "force_normal_in_grasp_phases_N": round(fn_grasp, 6),
        "cube_weight_force_N": round(a.cube_mass_kg * 9.81, 6),
        "track_rms_rad": (round(sum(track_vals) / len(track_vals), 6) if track_vals else "not_applicable_keyframe_or_static_reference"),
        "track_rms_tick_max": (round(max(track_vals), 6) if track_vals else None),
        "fell": fell,
        "root_z_min_m": round(min(rootz), 6),
        "root_z_max_m": round(max(rootz), 6),
        "root_z_range_m": round(max(rootz) - min(rootz), 6),
        "up_z_min": round(min(upz), 6),
        "final_lift_m": round(lift[-1], 6),
    }
    comp = (
        out["gap_at_trigger_m"] <= 0.06
        and out["lift_sustained_tail1s_min_m"] >= 0.05
        and out["force_normal_N"] >= 0.9 * a.cube_mass_kg * 9.81
        and out["n_contact_bodies"] >= 2
    )
    out["success_composite_protocol"] = bool(comp)
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
