"""ws1 matrix driver: launch all runs (grasp / negctl / ideal / kp100 series).

Parallel subprocesses (default 12), nice 10, RLIMIT_AS 16 GiB, OMP_NUM_THREADS=1.
Logs: out/runs/<tag>.log  results: out/runs/<tag>.json (+ _traj.npz)
"""
import argparse
import concurrent.futures as cf
import os
import resource
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1_lib as L

PY = os.path.join(L.ROOT, "env", "bin", "python")
RUN = os.path.join(L.ROOT, "scripts", "ws1_run.py")


def job(edge, mode, seed, extra=()):
    tag = "e%02d_%s_%03d" % (edge, mode, seed)
    cmd = [PY, "-B", RUN, "--edge", str(edge), "--seed", str(seed), "--mode", mode,
           "--lam-extra", "0.06", "--tag", tag] + list(extra)
    return tag, cmd


def build_jobs():
    jobs = []
    for e in (20, 25, 35):
        for s in range(10):
            jobs.append(job(e, "grasp", s))
        for s in range(3):
            jobs.append(job(e, "negctl", s))
        for s in range(2):
            jobs.append(job(e, "ideal", s))
        for s in range(5):
            jobs.append(job(e, "grasp", s, ("--hand-kp", "100", "--tag-suffix")))
    # fix tags for kp100 (job() already made tag e..grasp..; rename)
    fixed = []
    for tag, cmd in jobs:
        if "--tag-suffix" in cmd:
            cmd = [c for c in cmd if c != "--tag-suffix"]
            newtag = tag + "_kp100"
            idx = cmd.index("--tag")
            cmd[idx + 1] = newtag
            tag = newtag
        fixed.append((tag, cmd))
    return fixed


def run_one(item):
    tag, cmd = item
    log = os.path.join(L.RUNS_DIR, tag + ".log")
    env = dict(os.environ)
    env.update({"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "MUJOCO_GL": "disable", "PYOPENGL_PLATFORM": "glx"})
    env.pop("LD_LIBRARY_PATH", None)

    def _pre():
        os.nice(10)
        resource.setrlimit(resource.RLIMIT_AS, (16 << 30, 16 << 30))

    with open(log, "w") as lf:
        rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env,
                             preexec_fn=_pre)
    return tag, rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--par", type=int, default=12)
    args = ap.parse_args()
    os.makedirs(L.RUNS_DIR, exist_ok=True)
    jobs = build_jobs()
    print("jobs:", len(jobs), "par:", args.par)
    done = 0
    bad = []
    with cf.ThreadPoolExecutor(max_workers=args.par) as ex:
        for tag, rc in ex.map(run_one, jobs):
            done += 1
            if rc != 0:
                bad.append((tag, rc))
            if done % 10 == 0 or rc != 0:
                print("done %d/%d rc!=0:%s" % (done, len(jobs), bad[-3:]))
    print("ALL_DONE jobs=%d failures=%d %s" % (len(jobs), len(bad), bad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
