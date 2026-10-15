import json
import os
import subprocess

import numpy as np

MINE = "/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base/rep/out/e35n_00_06"
SRC = "/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/rep/out/e35n_00_06"
print("=== [G] wrist_target: NaN placement check ===")
za = np.load(MINE + "/trajectory.npz", allow_pickle=False)
zb = np.load(SRC + "/trajectory.npz", allow_pickle=False)
x, y = za["wrist_target"], zb["wrist_target"]
print("nan count mine=%d src=%d  nan mask identical=%s" % (
    int(np.isnan(x).sum()), int(np.isnan(y).sum()), bool(np.array_equal(np.isnan(x), np.isnan(y)))))
print("equal ignoring nan:", bool(np.array_equal(x, y, equal_nan=True)))
fin = np.isfinite(x) & np.isfinite(y)
print("finite entries: n=%d max_abs_diff=%.3e" % (fin.sum(),
      np.max(np.abs(x[fin] - y[fin])) if fin.sum() else 0.0))

print()
print("=== [H] result.json diff categorization ===")
a = json.load(open(MINE + "/result.json"))
b = json.load(open(SRC + "/result.json"))
diffs = []


def walk(u, v, p):
    if isinstance(u, dict) and isinstance(v, dict):
        for k in sorted(set(u) | set(v)):
            walk(u.get(k, "<missing>"), v.get(k, "<missing>"), p + "/" + str(k))
    elif isinstance(u, list) and isinstance(v, list):
        if len(u) != len(v):
            diffs.append((p + "/len", len(u), len(v)))
        for i, (ui, vi) in enumerate(zip(u, v)):
            walk(ui, vi, p + "[%d]" % i)
    else:
        if isinstance(u, float) and isinstance(v, float):
            if u == v:
                return
        elif u == v:
            return
        diffs.append((p, u, v))


walk(a, b, "")
cats = {}
for p, u, v in diffs:
    if "/execution_cycle_latency/" in p:
        c = "execution_cycle_latency (wall-clock)"
    elif "source" in p or "path" in p.lower() or "dir" in p.lower() or "xml" in p.lower() or "sha" in p.lower():
        c = "path/sha/runtime_stamp identity strings"
    else:
        c = "OTHER"
    cats.setdefault(c, []).append(p)
for c, ps in cats.items():
    print("  %-42s n=%d" % (c, len(ps)))
    if c == "OTHER":
        for p in ps:
            print("     ", p)
print("  NOTE: source_npz path field is under /source/... and differs by sandbox path (expected).")

print()
print("=== [I] g1_free_grasp.xml: what differs (mine vs src) ===")
p1, p2 = MINE + "/g1_free_grasp.xml", SRC + "/g1_free_grasp.xml"
l1 = open(p1, encoding="utf-8").read().splitlines()
l2 = open(p2, encoding="utf-8").read().splitlines()
print("lines mine=%d src=%d" % (len(l1), len(l2)))
nd = 0
for i, (u, v) in enumerate(zip(l1, l2)):
    if u != v:
        nd += 1
        if nd <= 5:
            print("  L%d mine: %s" % (i + 1, u.strip()[:150]))
            print("  L%d src : %s" % (i + 1, v.strip()[:150]))
print("differing lines: %d" % nd)

print()
print("=== [J] scene.xml sha compare ===")
import hashlib


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


print("scene.xml mine=%s" % sha(p1.replace("g1_free_grasp.xml", "scene.xml")))
print("scene.xml src =%s" % sha(p2.replace("g1_free_grasp.xml", "scene.xml")))

print()
print("=== [K] SOURCE READ-ONLY PROOF (no writes to source sandbox) ===")
print("source fixE_tally.csv mtime:", subprocess.run(
    ["stat", "-c", "%y %s", "/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/fixE_tally.csv"],
    capture_output=True, text=True).stdout.strip())
print("source run_fixE.sh sha:", subprocess.run(
    ["sha256sum", "/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/run_fixE.sh"],
    capture_output=True, text=True).stdout.split()[0])
for d in ["/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/rep/out",
          "/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/raw"]:
    n = len(os.listdir(d))
    newest = max((os.path.getmtime(os.path.join(d, f)), f) for f in os.listdir(d))
    import datetime
    print("%s entries=%d newest=%s (%s)" % (d, n, newest[1],
          datetime.datetime.fromtimestamp(newest[0]).strftime("%Y-%m-%d %H:%M:%S")))
st = os.stat("/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/rep/out/e35n_00_06")
print("source anchor out dir mtime:", datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"))
print("source progress.txt mtime:", datetime.datetime.fromtimestamp(
    os.path.getmtime("/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/progress.txt")).strftime("%Y-%m-%d %H:%M:%S"))
