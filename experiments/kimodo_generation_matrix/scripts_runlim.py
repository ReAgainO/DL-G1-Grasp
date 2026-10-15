#!/usr/bin/env python3
"""x04_runlim.py -- per-process hard resource cap + wall/RSS probe for one KIMODO CLI call."""
import json, os, resource, subprocess, sys, time

def main():
    if len(sys.argv) < 3:
        print("usage: x04_runlim.py <log_path> <argv...>", file=sys.stderr)
        return 2
    log_path = sys.argv[1]
    argv = sys.argv[2:]
    gib = float(os.environ.get("X04_RLIMIT_AS_GIB", "64"))
    lim = int(gib * 2**30)
    prev = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    t0 = time.perf_counter()
    with open(log_path, "wb") as fh:
        p = subprocess.Popen(argv, stdout=fh, stderr=subprocess.STDOUT, env=os.environ)
        rc = p.wait()
    wall = time.perf_counter() - t0
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    print(json.dumps({
        "rc": int(rc),
        "wall_s": round(wall, 2),
        "maxrss_kb": int(ru.ru_maxrss),
        "rlimit_as_gib": gib,
        "rlimit_as_bytes": lim,
        "rlimit_as_before": [str(prev[0]), str(prev[1])],
        "ru_maxrss_scope": "RUSAGE_CHILDREN of this wrapper (one child only)",
        "log": log_path,
    }))
    return 0

if __name__ == "__main__":
    sys.exit(main())
