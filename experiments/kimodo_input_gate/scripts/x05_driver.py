#!/usr/bin/env python3
"""x05eval driver: feed generated 36-column qpos CSVs into the SONIC-in-MuJoCo
generated-motion closed loop (x02eval's verified patched runner copy) and emit
the protocol section-2 metric table.

CPU only. No MUJOCO_GL. Threads pinned to 1 per process; parallelism is by
PROCESS (x02 lesson: OMP=1 + process-level fan-out).
"""
import argparse
import csv
import concurrent.futures as cf
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PY = "/data/group4/20261004-205550-qoder-1280b420/env/bin/python"
D = Path("/data/group4/20261006-055934-qoder-x05eval")
BRIDGE_STOCK = D / "bridge"
BRIDGE_TRACE = D / "bridge-trace"
RUNS = D / "runs"

# x02's pinned finger-FSM schedule for a 4.0 s clip (report A.1 command 2).
FSM = {"close_start": 2.2, "close_duration": 0.6, "lift_start": 2.8,
       "lift_duration": 1.0}

METRIC_KEYS = ["gap_min_m", "gap_at_trigger_m", "trigger_time_s", "lift_max_m",
               "lift_sustained_tail1s_min_m",
               "lift_sustained_ge5cm_trailing_seconds", "n_contact_bodies",
               "force_normal_N", "force_normal_in_grasp_phases_N",
               "track_rms_rad", "fell", "root_z_range_m", "up_z_min",
               "final_lift_m", "success_composite_protocol",
               "gap_min_fingertip_m", "samples", "episode_seconds"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def runner_args_gen(csv_path, duration, source, source_fps, no_grip, trace):
    a = ["--trace-csv", str(trace), "--duration", "%g" % duration,
         "--allow-failure", "--motion-source", source,
         "--motion-file", str(csv_path), "--source-fps", "%g" % source_fps,
         "--close-start", "%g" % FSM["close_start"],
         "--close-duration", "%g" % FSM["close_duration"],
         "--lift-start", "%g" % FSM["lift_start"],
         "--lift-duration", "%g" % FSM["lift_duration"]]
    if no_grip:
        a.append("--no-grip")
    return " ".join(a)


def run_batch(tag, bridge, repeats, runner_args, input_csv, mode, base,
              export=False, trace_rel=None):
    cmd = [PY, str(D / "scripts/run_batch.py"), "--bridge", str(bridge),
           "--py", PY, "--tag", tag, "--repeats", str(repeats),
           "--mode", mode, "--base", base,
           "--lib", str(bridge / "policy_state_dict.pt"),
           "--out-root", str(RUNS),
           "--runner-args", runner_args]
    if input_csv:
        cmd += ["--input-csv", str(input_csv)]
    if export:
        cmd += ["--export"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    sj = RUNS / tag / "summary.json"
    summary = json.loads(sj.read_text()) if sj.is_file() else None
    return p.returncode, p.stdout, p.stderr, summary


def evaluate_cell(name, csv_path, source, source_fps, duration, meta,
                  no_grip=False, repeats=1, index=None):
    tag = name + ("_OFF" if no_grip else "")
    if index is not None:
        tag = tag + "_rep%d" % index
    tagd = RUNS / tag
    rdirs = [tagd / ("r%02d" % (i + 1)) for i in range(repeats)]
    for rd in rdirs:
        rd.mkdir(parents=True, exist_ok=True)
    trace = rdirs[0] / "trace.csv"
    ra = runner_args_gen(csv_path, duration, source, source_fps, no_grip, trace)
    rc, out, err, summary = run_batch(tag, BRIDGE_TRACE, repeats, ra,
                                      csv_path, "sonic-closed", "pinned")
    rec = {"tag": tag, "rc": rc, "stderr_tail": (err or "")[-600:],
           "no_grip": no_grip, "meta": meta,
           "input_csv": str(csv_path), "input_csv_sha256": sha(csv_path),
           "source": source, "source_fps": source_fps, "duration_s": duration,
           "fsm": FSM, "repeats": repeats}
    if summary:
        rec["runtime_stamp"] = summary["runtime_stamp"]
        rec["runs"] = summary["runs"]
        rec["summary_stats"] = summary["summary"]
        rec["result_line"] = summary["runs"][0].get("result_line")
        rec["control_mode"] = summary["runs"][0].get("control_mode")
        rec["success_runner"] = summary["runs"][0].get("success_raw")
        rec["force_single_contact_max_N"] = summary["runs"][0].get("max_normal_force")
        rec["lifted_height_runner_m"] = summary["runs"][0].get("lifted_height")
        rec["n_contact_bodies_runner"] = summary["runs"][0].get("max_contact_bodies")
        rec["contact_bodies"] = summary["runs"][0].get("contact_bodies")
        rec["wall_seconds"] = summary["runs"][0].get("wall_seconds")
        rec["reference_window_info"] = None
    # protocol metrics from the trace
    mpath = rdirs[0] / "metrics.json"
    if trace.is_file():
        mp = subprocess.run([PY, str(D / "scripts/trace_metrics.py"),
                             "--trace", str(trace), "--out", str(mpath)],
                            capture_output=True, text=True)
        rec["trace_metrics_rc"] = mp.returncode
        if mp.returncode != 0:
            rec["trace_metrics_error"] = (mp.stderr or "")[-600:]
        if mpath.is_file():
            met = json.loads(mpath.read_text())
            for k in METRIC_KEYS:
                rec[k] = met.get(k)
    else:
        rec["trace_missing"] = True
    (tagd / "cell_result.json").write_text(json.dumps(rec, indent=2, default=str))
    return rec


def read_manifest(path, kind):
    rows = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    return rows


def build_jobs(kind, rows, root):
    jobs = []
    for r in rows:
        cid = r["cell_id"]
        cands = [root / "gen" / (cid + ".csv"), root / (cid + ".csv")]
        cp = next((c for c in cands if c.is_file()), None)
        if cp is None:
            jobs.append((cid, None, r, "CSV_NOT_FOUND"))
            continue
        if sha(cp)[:12] != r["csv_sha256"][:12]:
            jobs.append((cid, cp, r, "CSV_SHA_MISMATCH"))
            continue
        jobs.append((cid, cp, r, None))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", required=True,
                    help="x01|x04|x06|c4|c2|c1|c4trace|all")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cells", default="", help="comma list filter")
    a = ap.parse_args()
    RUNS.mkdir(parents=True, exist_ok=True)
    only = set(x for x in a.cells.split(",") if x)

    jobs = []
    if a.which in ("x01", "all"):
        root = Path("/data/group4/20261006-042504-qoder-x01gen")
        rows = read_manifest(root / "gen_manifest.csv", "ardy")
        for cid, cp, r, bad in build_jobs("ardy", rows, root):
            if bad:
                jobs.append({"cell": cid, "skip": bad, "csv": str(cp) if cp else None})
                continue
            jobs.append({"cell": "ARDY_" + cid, "csv": cp, "source": "ardy",
                         "fps": 25.0, "dur": float(r["duration_s"]),
                         "meta": {"batch": "x01gen", "cell_id": cid,
                                  "prompt_id": r["prompt_id"], "seed": r["seed"],
                                  "arm": r["arm"], "cfg_text": r["cfg_text"],
                                  "cfg_constr": r["cfg_constr"],
                                  "diffusion_steps": r["diffusion_steps"],
                                  "frames": r["frames"], "cols": r["cols"],
                                  "gen_device": r["device"], "dtype": r["dtype"],
                                  "prompt_sha256": r["prompt_sha256"],
                                  "csv_sha256": r["csv_sha256"],
                                  "lim_cells_beyond_tol": r["lim_cells_beyond_tol"],
                                  "base_table_overlap_frames": r["base_table_overlap_frames"],
                                  "root_z_lo": r["root_z_lo"], "root_z_hi": r["root_z_hi"],
                                  "gen_loader": r["loader"], "model": r["model_preset"]}})
    if a.which in ("x04", "all"):
        root = Path("/data/group4/20261006-045000-qoder-x04kimodo")
        p = root / "gen_manifest.csv"
        if p.is_file():
            rows = read_manifest(p, "kimodo")
            for cid, cp, r, bad in build_jobs("kimodo", rows, root):
                if bad:
                    jobs.append({"cell": cid, "skip": bad, "csv": str(cp) if cp else None})
                    continue
                jobs.append({"cell": "KIM_" + cid, "csv": cp, "source": "kimodo",
                             "fps": float(r["fps"]),
                             "dur": float(r["duration_s"]),
                             "meta": {"batch": "x04kimodo", "cell_id": cid,
                                      "prompt_id": r["prompt_id"], "seed": r["seed"],
                                      "arm": r["arm"], "cfg_text": r["cfg_text"],
                                      "cfg_constr": r.get("cfg_constr", ""),
                                      "diffusion_steps": r["diffusion_steps"],
                                      "frames": r["frames"], "cols": r["cols"],
                                      "gen_device": r["device"], "dtype": "n/a",
                                      "prompt_sha256": r["prompt_sha256"],
                                      "csv_sha256": r["csv_sha256"],
                                      "lim_cells_beyond_tol": r["lim_cells_beyond_tol"],
                                      "base_table_overlap_frames": r["base_table_overlap_frames"],
                                      "root_z_lo": r["root_z_lo"], "root_z_hi": r["root_z_hi"],
                                      "gen_loader": r["loader"], "model": r["model"]}})
    if a.which == "x06":
        root = Path("/data/group4/20261006-055932-qoder-x06canon")
        p = root / "gen_manifest.csv"
        if not p.is_file():
            print("[SKIP] x06canon manifest absent")
            return
        rows = read_manifest(p, "canon")
        # canonical arm source/fps auto-detected from the model column
        for cid, cp, r, bad in build_jobs("canon", rows, root):
            if bad:
                jobs.append({"cell": cid, "skip": bad, "csv": str(cp) if cp else None})
                continue
            model = (r.get("model") or r.get("model_preset") or "").lower()
            src = "kimodo" if "kimodo" in model else "ardy"
            fps = float(r.get("fps") or (30.0 if src == "kimodo" else 25.0))
            jobs.append({"cell": "CAN_" + cid, "csv": cp, "source": src,
                         "fps": fps, "dur": float(r["duration_s"]),
                         "meta": {"batch": "x06canon", "cell_id": cid,
                                  "prompt_id": r.get("prompt_id", ""),
                                  "seed": r.get("seed", ""),
                                  "arm": r.get("arm", ""),
                                  "cfg_text": r.get("cfg_text", ""),
                                  "cfg_constr": r.get("cfg_constr", ""),
                                  "diffusion_steps": r.get("diffusion_steps", ""),
                                  "frames": r.get("frames", ""),
                                  "cols": r.get("cols", ""),
                                  "gen_device": r.get("device", ""),
                                  "dtype": r.get("dtype", "n/a"),
                                  "prompt_sha256": r.get("prompt_sha256", ""),
                                  "csv_sha256": r.get("csv_sha256", ""),
                                  "lim_cells_beyond_tol": r.get("lim_cells_beyond_tol", ""),
                                  "base_table_overlap_frames": r.get("base_table_overlap_frames", ""),
                                  "root_z_lo": r.get("root_z_lo", ""),
                                  "root_z_hi": r.get("root_z_hi", ""),
                                  "gen_loader": r.get("loader", ""),
                                  "model": r.get("model", r.get("model_preset", ""))}})
    if only:
        jobs = [j for j in jobs if j["cell"] in only or j.get("cell_id") in only]

    print("[PLAN] %d jobs, %d workers" % (len(jobs), a.workers))
    results = []
    skips = [j for j in jobs if j.get("skip")]
    for s in skips:
        results.append({"tag": s["cell"], "skip": s["skip"],
                        "input_csv": s.get("csv")})
        print("[SKIP] %s %s" % (s["cell"], s["skip"]))
    real = [j for j in jobs if not j.get("skip")]
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(evaluate_cell, j["cell"], j["csv"], j["source"],
                          j["fps"], j["dur"], j["meta"]): j for j in real}
        for f in cf.as_completed(futs):
            j = futs[f]
            try:
                rec = f.result()
            except Exception as e:
                rec = {"tag": j["cell"], "exception": repr(e)}
            results.append(rec)
            print("[CELL] %s rc=%s ctrl=%s lift_tail1s=%s gapmin=%s ncb=%s fn=%s trms=%s succ=%s" %
                  (rec.get("tag"), rec.get("rc"), rec.get("control_mode"),
                   rec.get("lift_sustained_tail1s_min_m"), rec.get("gap_min_m"),
                   rec.get("n_contact_bodies"), rec.get("force_normal_N"),
                   rec.get("track_rms_rad"), rec.get("success_composite_protocol")),
                  flush=True)
    write_table(a.which, results)
    print("[DONE] %d records" % len(results))


TABLE_COLS = ["tag", "batch", "cell_id", "prompt_id", "seed", "arm", "cfg_text",
              "diffusion_steps", "model", "source", "source_fps", "duration_s",
              "input_csv", "input_csv_sha256", "control_mode", "rc",
              "wall_seconds", "n_contact_bodies", "contact_bodies",
              "force_normal_N", "force_single_contact_max_N",
              "gap_min_m", "gap_at_trigger_m", "trigger_time_s", "lift_max_m",
              "lifted_height_runner_m", "lift_sustained_tail1s_min_m",
              "lift_sustained_ge5cm_trailing_seconds", "track_rms_rad",
              "fell", "root_z_range_m", "up_z_min", "final_lift_m",
              "success_runner", "success_composite_protocol",
              "lim_cells_beyond_tol", "base_table_overlap_frames",
              "mujoco_version", "library_sha", "model_sha", "scene_generator_sha",
              "runner_sha", "timestep", "base", "repeat_index", "skip",
              "trace_metrics_error", "stderr_tail"]


def write_table(which, results):
    out = D / ("table_%s.csv" % which)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=TABLE_COLS, extrasaction="ignore")
        w.writeheader()
        for rec in results:
            row = {k: "" for k in TABLE_COLS}
            m = rec.get("meta") or {}
            rs = rec.get("runtime_stamp") or {}
            row["tag"] = rec.get("tag")
            row["skip"] = rec.get("skip") or rec.get("exception") or ""
            row["input_csv"] = rec.get("input_csv", m.get("csv", ""))
            for k in ("batch", "cell_id", "prompt_id", "seed", "arm",
                      "diffusion_steps", "model", "contact_bodies",
                      "lim_cells_beyond_tol", "base_table_overlap_frames",
                      "force_single_contact_max_N", "lifted_height_runner_m",
                      "control_mode", "rc", "wall_seconds", "n_contact_bodies",
                      "gap_min_m", "gap_at_trigger_m", "trigger_time_s",
                      "lift_max_m", "lift_sustained_tail1s_min_m",
                      "lift_sustained_ge5cm_trailing_seconds", "track_rms_rad",
                      "fell", "root_z_range_m", "up_z_min", "final_lift_m",
                      "success_runner", "success_composite_protocol",
                      "force_normal_N"):
                if k in m:
                    row[k] = m[k]
                elif k in rec:
                    row[k] = rec[k]
            row["cfg_text"] = m.get("cfg_text", "")
            row["source"] = rec.get("source", "")
            row["source_fps"] = rec.get("source_fps", "")
            row["duration_s"] = rec.get("duration_s", "")
            row["input_csv_sha256"] = rec.get("input_csv_sha256",
                                              rs.get("input_csv_sha256", ""))
            row["mujoco_version"] = rs.get("mujoco_version", "")
            row["library_sha"] = (rs.get("library_sha") or "")[:64]
            row["model_sha"] = (rs.get("model_sha") or "")[:64]
            row["scene_generator_sha"] = (rs.get("scene_generator_sha") or "")[:64]
            row["runner_sha"] = (rs.get("runner_sha") or "")[:64]
            row["timestep"] = rs.get("timestep", "")
            row["base"] = rs.get("base", "")
            row["repeat_index"] = (rec.get("runs") or [{}])[0].get("repeat_index", 1)
            row["trace_metrics_error"] = rec.get("trace_metrics_error", "")
            row["stderr_tail"] = (rec.get("stderr_tail") or "").replace("\n", " ")[:300]
            w.writerow(row)
    print("[TABLE] %s bytes=%d" % (out, out.stat().st_size))


if __name__ == "__main__":
    main()
