#!/usr/bin/env python3
# Cold-start episode driver for the SONIC-in-MuJoCo grasp evaluator.
# Each repeat is a fresh subprocess (cold start). Records rc, wall, child PID,
# RSS, stdout sha, parsed [RESULT]/[CONTROL] metrics, exported manifest metrics
# (full precision) and a runtime_stamp.
import argparse
import hashlib
import json
import os
import resource
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path


def set_limits(as_gib, cpu_s):
    lim = int(as_gib * (1 << 30))
    resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_s), int(cpu_s) + 30))


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def kv_from_line(line):
    out = {}
    for tok in line.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
    return out


def parse_stdout(text):
    res = {}
    ctrl = {}
    for line in text.splitlines():
        if line.startswith("[RESULT] "):
            res = kv_from_line(line[9:])
        elif line.startswith("[CONTROL] "):
            ctrl = kv_from_line(line[10:])
    return res, ctrl


def to_float(v):
    if v is None:
        return None
    m = re.search(r"-?[0-9]*\.?[0-9]+", str(v))
    try:
        return float(m.group(0)) if m else None
    except (TypeError, ValueError):
        return None


import re


def result_line_of(text):
    for line in text.splitlines():
        if line.startswith("[RESULT] "):
            return line
    return ""


PROBE_ENV = (
    "import sys,json,mujoco,numpy;"
    "d={'mujoco':mujoco.__version__,'numpy':numpy.__version__,"
    "'python':sys.version.split()[0],'exe':sys.executable};"
    "d['torch']=getattr(__import__('torch','x','x',['']),'__version__','absent');"
    "print(json.dumps(d))"
)

PROBE_MODEL = (
    "import mujoco,json;"
    "m=mujoco.MjModel.from_xml_path('g1/scene_grasp_hand.xml');"
    "print(json.dumps({'timestep':m.opt.timestep,'nq':m.nq,'nv':m.nv,'nu':m.nu,"
    "'nbody':m.nbody,'integrator':int(m.opt.integrator),'cone':int(m.opt.cone),"
    "'solver':int(m.opt.solver),'multiccd':bool(m.opt.enableflags & 32)}))"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bridge", required=True)
    ap.add_argument("--py", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--runner-args", default="")
    ap.add_argument("--pythonpath", default="")
    ap.add_argument("--as-gib", type=float, default=16.0)
    ap.add_argument("--cpu-cap", type=float, default=240.0)
    ap.add_argument("--wall-timeout", type=float, default=300.0)
    ap.add_argument("--mode", default="direct")
    ap.add_argument("--base", default="pinned")
    ap.add_argument("--input-csv", default="")
    ap.add_argument("--lib", default="")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--out-root",
                    default="/data/group4/20261006-042506-qoder-x02eval/runs")
    args = ap.parse_args()

    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (int(args.as_gib) << 30, int(args.as_gib) << 30))
    print("[RLIMIT] self RLIMIT_AS was soft=%s hard=%s -> now soft=%d" %
          (soft, hard, resource.getrlimit(resource.RLIMIT_AS)[0]))

    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["NUMEXPR_NUM_THREADS"] = "1"
    env["VECLIB_MAXIMUM_THREADS"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env.pop("MUJOCO_GL", None)
    env.pop("CUDA_VISIBLE_DEVICES", None)
    if args.pythonpath:
        env["PYTHONPATH"] = args.pythonpath
    else:
        env.pop("PYTHONPATH", None)

    probe = subprocess.run([args.py, "-c", PROBE_ENV], capture_output=True,
                           text=True, env=env)
    stamp_env = json.loads(probe.stdout.strip().splitlines()[-1])
    mprobe = subprocess.run([args.py, "-c", PROBE_MODEL], capture_output=True,
                            text=True, env=env, cwd=args.bridge)
    stamp_model = json.loads(mprobe.stdout.strip().splitlines()[-1])
    print("[STAMP] " + json.dumps({**stamp_env, **stamp_model}))

    scene_sha = sha_file(Path(args.bridge) / "g1" / "scene_grasp_hand.xml")
    model_sha = sha_file(Path(args.bridge) / "g1" / "g1_29dof_with_hand.xml")
    runner_sha = sha_file(Path(args.bridge) / "runners" / "run_grasp.py")
    lib_sha = sha_file(args.lib) if args.lib and Path(args.lib).is_file() else None
    input_sha = sha_file(args.input_csv) if args.input_csv and Path(args.input_csv).is_file() else None

    tag_dir = Path(args.out_root) / args.tag
    tag_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    extra = shlex.split(args.runner_args)
    rss_before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

    for i in range(1, args.repeats + 1):
        rd = tag_dir / ("r%02d" % i)
        rd.mkdir(parents=True, exist_ok=True)
        cmd = [args.py, "runners/run_grasp.py", "--headless", "--quiet"] + extra
        man_out = None
        if args.export:
            csv_out = rd / "baseline.csv"
            man_out = rd / "manifest.json"
            cmd += ["--export-baseline-csv", str(csv_out),
                    "--export-baseline-manifest", str(man_out)]
        t0 = time.monotonic()
        proc = subprocess.Popen(cmd, cwd=args.bridge, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True,
                                preexec_fn=lambda: set_limits(args.as_gib, args.cpu_cap))
        timed_out = False
        try:
            out, _ = proc.communicate(timeout=args.wall_timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            out, _ = proc.communicate()
        wall = time.monotonic() - t0
        (rd / "stdout.log").write_text(out)
        res, ctrl = parse_stdout(out)
        rline = result_line_of(out)
        cb = re.search(r"contact_bodies=(\[[^\]]*\])", rline)
        row = {
            "repeat_index": i,
            "tag": args.tag,
            "rc": proc.returncode,
            "timed_out": timed_out,
            "wall_seconds": round(wall, 3),
            "child_pid": proc.pid,
            "stdout_sha256": hashlib.sha256(out.encode()).hexdigest(),
            "result_line": rline,
            "result_line_sha256": hashlib.sha256(rline.encode()).hexdigest(),
            "success_raw": res.get("success"),
            "no_grip_raw": res.get("no_grip"),
            "lifted_height": to_float(res.get("lifted_height")),
            "final_clearance": to_float(res.get("final_clearance")),
            "max_normal_force": to_float(res.get("max_normal_force")),
            "max_contact_bodies": to_float(res.get("max_contact_bodies")),
            "max_contacts": to_float(res.get("max_contacts")),
            "lift_contact_time": to_float(res.get("lift_contact_time")),
            "contact_bodies": cb.group(1) if cb else None,
            "control_mode": ctrl.get("control_mode"),
            "fixed_arm_override_count": ctrl.get("fixed_arm_override_count"),
            "fixed_arm_pd_write_count": ctrl.get("fixed_arm_pd_write_count"),
            "unique_action_hashes": ctrl.get("unique_action_hashes"),
            "action_count": ctrl.get("action_count"),
            "stdout_lines": len(out.splitlines()),
        }
        if man_out and man_out.is_file():
            man = json.loads(man_out.read_text())
            row["manifest_full_precision"] = man.get("acceptance_metrics")
            row["manifest_csv_sha256"] = man.get("csv", {}).get("sha256")
            row["manifest_provenance"] = man.get("provenance")
        rows.append(row)
        print("[RUN] idx=%d rc=%s wall=%.2fs success=%s lift=%s force=%s bodies=%s" %
              (i, proc.returncode, wall, row["success_raw"], row["lifted_height"],
               row["max_normal_force"], row["contact_bodies"]), flush=True)

    rss_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    payload = {
        "tag": args.tag,
        "runtime_stamp": {
            "mujoco_version": stamp_env["mujoco"],
            "sys_executable": stamp_env["exe"],
            "python_version": stamp_env["python"],
            "numpy_version": stamp_env["numpy"],
            "torch_version": stamp_env.get("torch"),
            "model_sha": model_sha,
            "scene_generator_sha": scene_sha,
            "runner_sha": runner_sha,
            "library_sha": lib_sha,
            "input_csv_sha256": input_sha,
            "timestep": stamp_model["timestep"],
            "nq_nv_nu": [stamp_model["nq"], stamp_model["nv"], stamp_model["nu"]],
            "integrator_cone_solver": [stamp_model["integrator"], stamp_model["cone"], stamp_model["solver"]],
            "multiccd": stamp_model["multiccd"],
            "mode": args.mode,
            "base": args.base,
            "runner_args": args.runner_args,
            "export_used": bool(args.export),
            "pythonpath_shim": args.pythonpath or None,
            "rlimit_as_gib": args.as_gib,
            "thread_env": {k: env[k] for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
            "mujoco_gl": env.get("MUJOCO_GL", "unset"),
        },
        "repeats": args.repeats,
        "ru_maxrss_children_kb": rss_peak,
        "ru_maxrss_before_kb": rss_before,
        "runs": rows,
    }
    def stats_of(key):
        vals = [r[key] for r in rows if isinstance(r.get(key), float)]
        if not vals:
            return None
        return {"n": len(vals), "min": min(vals), "median": statistics.median(vals),
                "max": max(vals), "range": max(vals) - min(vals),
                "distinct_round6": sorted({round(v, 6) for v in vals})}

    succ = [r["success_raw"] for r in rows if r["success_raw"] is not None]
    flips = sum(1 for a, b in zip(succ, succ[1:]) if a != b)
    fails = [r["repeat_index"] for r in rows if r["success_raw"] != "True"]
    payload["summary"] = {
        "success_counts": {str(k): succ.count(str(k)) for k in ("True", "False")},
        "success_flips_adjacent": flips,
        "failed_repeat_indices": fails,
        "distinct_stdout_shas": len({r["stdout_sha256"] for r in rows}),
        "distinct_result_line_shas": len({r["result_line_sha256"] for r in rows}),
        "distinct_manifest_csv_shas": len({r.get("manifest_csv_sha256") for r in rows
                                           if r.get("manifest_csv_sha256")}),
        "lifted_height": stats_of("lifted_height"),
        "final_clearance": stats_of("final_clearance"),
        "max_normal_force": stats_of("max_normal_force"),
        "max_contact_bodies": stats_of("max_contact_bodies"),
        "lift_contact_time": stats_of("lift_contact_time"),
        "wall_seconds": stats_of("wall_seconds"),
        "rc_counts": {str(r["rc"]): sum(1 for x in rows if x["rc"] == r["rc"]) for r in rows},
    }
    out_json = tag_dir / "summary.json"
    out_json.write_text(json.dumps(payload, indent=2, default=str))
    print("[DONE] %s bytes=%d ru_maxrss_children_kb=%d" % (out_json, out_json.stat().st_size, rss_peak))
    print("[SELF_RU_MAXRSS_KB] %d" % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


if __name__ == "__main__":
    main()
