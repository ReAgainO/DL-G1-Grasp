"""ws1b matrix driver (pads-only variant).

Launches runs in parallel subprocesses (nice 10, RLIMIT_AS 16 GiB, single-thread
BLAS, MUJOCO_GL=disable), logs under out/runs/<tag>.log.

usage examples:
  python ws1b_matrix.py --sizes 20,25,35 --reps 10 --negctl 3 --ideal 2 --par 8
  python ws1b_matrix.py --sizes 25 --reps 8 --negctl 0 --ideal 0 --arm mu2 --extra "--pad-mu 2.0"
"""
import argparse
import concurrent.futures as cf
import os
import resource
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ws1b_lib as L

PY = os.path.join(L.W1_ROOT, "env", "bin", "python")
RUN = os.path.join(L.ROOT, "scripts", "ws1b_run.py")


def build_jobs(args):
    jobs = []
    extra = args.extra.split() if args.extra else []
    if args.placement:
        extra += ["--placement", args.placement]
    arm = ("_" + args.arm) if args.arm else ""
    for e in [int(v) for v in args.sizes.split(",")]:
        eextra = list(extra)
        if args.scene_suffix:
            eextra += ["--scene", os.path.join(L.MODEL_DIR,
                                               "ws1b_scene_%dmm_%s.xml" % (e, args.scene_suffix))]
        for s in range(args.reps):
            tag = "e%02d_grasp%s_%03d" % (e, arm, s)
            jobs.append((tag, ["--edge", str(e), "--seed", str(s), "--mode", "grasp"] + eextra))
        for s in range(args.negctl):
            tag = "e%02d_negctl%s_%03d" % (e, arm, s)
            jobs.append((tag, ["--edge", str(e), "--seed", str(s), "--mode", "negctl"] + eextra))
        for s in range(args.ideal):
            tag = "e%02d_ideal%s_%03d" % (e, arm, s)
            jobs.append((tag, ["--edge", str(e), "--seed", str(s), "--mode", "ideal"] + eextra))
    out = []
    for tag, a in jobs:
        cmd = [PY, "-B", RUN] + a + ["--lam-extra", args.lam_extra, "--tag", tag]
        if args.placement:
            cmd += ["--placement", args.placement]
        out.append((tag, cmd))
    return out


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
    ap.add_argument("--sizes", default="20,25,35")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--negctl", type=int, default=3)
    ap.add_argument("--ideal", type=int, default=2)
    ap.add_argument("--par", type=int, default=8)
    ap.add_argument("--lam-extra", default="0.06")
    ap.add_argument("--arm", default=None, help="arm name appended to tags (e.g. mu2)")
    ap.add_argument("--extra", default=None, help="extra args for ws1b_run.py, quoted")
    ap.add_argument("--placement", default=None)
    ap.add_argument("--scene-suffix", default=None, help="use ws1b_scene_<edge>mm_<suffix>.xml scenes")
    args = ap.parse_args()
    os.makedirs(L.RUNS_DIR, exist_ok=True)
    jobs = build_jobs(args)
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
