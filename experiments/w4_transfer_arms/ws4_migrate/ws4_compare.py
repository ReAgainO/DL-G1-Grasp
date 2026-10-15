import hashlib
import json

import numpy as np

MINE = "/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_base/rep/out/e35n_00_06"
SRC = "/data/group4/20261008-182000-qoder-7d11d1ae/rep_fixE/rep/out/e35n_00_06"
a = json.load(open(MINE + "/result.json"))
b = json.load(open(SRC + "/result.json"))


def sha(p):
    h = hashlib.sha256()
    h.update(open(p, "rb").read())
    return h.hexdigest()


print("=== [A] headline fields: mine vs source ===")
print("%-28s %-34s %-34s %s" % ("field", "mine(copy run)", "source(fixE)", "match"))
rows = [
    ("success", a.get("success"), b.get("success")),
    ("fail_reason", a.get("fail_reason"), b.get("fail_reason")),
    ("hold_min_lift_m", a.get("hold_min_lift_m"), b.get("hold_min_lift_m")),
    ("hold_slip_m", a.get("hold_slip_m"), b.get("hold_slip_m")),
    ("peak_external_force", a.get("peak_external_force"), b.get("peak_external_force")),
    ("gate_definition_version", a.get("gate_definition_version"), b.get("gate_definition_version")),
    ("legacy_success", a.get("legacy_success"), b.get("legacy_success")),
    ("final_support_by_geom_N", a.get("final_support_by_geom_N"), b.get("final_support_by_geom_N")),
    ("final_table_min_force_last100ms_N", a.get("final_table_min_force_last100ms_N"),
     b.get("final_table_min_force_last100ms_N")),
    ("release_height_drop_definition", a.get("release_height_drop_definition"), b.get("release_height_drop_definition")),
    ("tally lift_mm (round(ms*1000,1))", round(a.get("hold_min_lift_m") * 1000, 1),
     round(b.get("hold_min_lift_m") * 1000, 1)),
    ("tally slip_mm (round(ms*1000,2))", round(a.get("hold_slip_m") * 1000, 2),
     round(b.get("hold_slip_m") * 1000, 2)),
]
for k, x, y in rows:
    print("%-28s %-34s %-34s %s" % (k, repr(x), repr(y), "SAME" if x == y else "DIFF"))

print()
print("=== [B] gates (mine vs source) ===")
ga, gb = a["gates"], b["gates"]
allg = sorted(set(ga) | set(gb))
red_mine = sorted(k for k, v in ga.items() if not v)
red_src = sorted(k for k, v in gb.items() if not v)
print("n_gates mine=%d src=%d ; red_n mine=%d src=%d" % (len(ga), len(gb), len(red_mine), len(red_src)))
print("red gates mine:", red_mine)
print("red gates src :", red_src)
mismatch = [k for k in allg if ga.get(k) != gb.get(k)]
print("gate bool mismatches:", mismatch if mismatch else "NONE (all %d gates identical)" % len(allg))

print()
print("=== [C] full recursive leaf-diff of result.json (numeric/str/bool leaves) ===")
diffs = []


def walk(x, y, p):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            walk(x.get(k, "<missing>"), y.get(k, "<missing>"), p + "/" + str(k))
    elif isinstance(x, list) and isinstance(y, list):
        if len(x) != len(y):
            diffs.append((p + "/len", len(x), len(y)))
        for i, (xi, yi) in enumerate(zip(x, y)):
            walk(xi, yi, p + "[%d]" % i)
    else:
        if isinstance(x, float) and isinstance(y, float):
            if x == y:
                return
            diffs.append((p, x, y))
        elif x != y:
            diffs.append((p, repr(x)[:70], repr(y)[:70]))


walk(a, b, "")
print("total leaf diffs: %d" % len(diffs))
nonpath = [d for d in diffs if not any(s in d[0] for s in ("/source/", "path", "dir", "file"))]
print("diffs excluding path-like keys: %d" % len(nonpath))
for d in nonpath[:40]:
    print("  ", d)
print("-- path-like diffs (first 10) --")
for d in [d for d in diffs if d not in nonpath][:10]:
    print("  ", d[0], "|", str(d[1])[:60], "|", str(d[2])[:60])

print()
print("=== [D] trajectory.npz numeric determinism (bit + value) ===")
print("sha256 mine:", sha(MINE + "/trajectory.npz"))
print("sha256 src :", sha(SRC + "/trajectory.npz"))
za = np.load(MINE + "/trajectory.npz", allow_pickle=False)
zb = np.load(SRC + "/trajectory.npz", allow_pickle=False)
print("arrays mine:", list(za.keys()))
for k in za.keys():
    if k in zb:
        x, y = za[k], zb[k]
        if x.shape != y.shape:
            print("  %-12s SHAPE DIFF %s vs %s" % (k, x.shape, y.shape))
            continue
        if x.dtype.kind in "fiu":
            d = np.max(np.abs(x.astype(np.float64) - y.astype(np.float64))) if x.size else 0.0
            print("  %-12s shape=%-18s max_abs_diff=%.3e  bitwise_equal=%s" % (k, str(x.shape), d, np.array_equal(x, y)))
        else:
            print("  %-12s shape=%-18s dtype=%s equal=%s" % (k, str(x.shape), x.dtype, np.array_equal(x, y)))

print()
print("=== [E] artifact sizes (mine vs src) ===")
import os
for f in ["result.json", "trajectory.npz", "telemetry.csv.gz", "cube_contacts.csv.gz", "scene.xml",
          "g1_free_grasp.xml", "contact-audit.json", "balance-audit.json"]:
    p1, p2 = MINE + "/" + f, SRC + "/" + f
    s1 = os.path.getsize(p1) if os.path.exists(p1) else -1
    s2 = os.path.getsize(p2) if os.path.exists(p2) else -1
    print("  %-24s mine=%-10d src=%-10d %s" % (f, s1, s2, "SAME" if s1 == s2 else "SIZE_DIFF"))

print()
print("=== [F] runtime versions actually used ===")
import mujoco
print("mujoco:", mujoco.__version__, " numpy:", np.__version__)
print("mine runtime_stamp.library_versions:", json.dumps(a["runtime_stamp"].get("library_versions")))
print("src  runtime_stamp.library_versions:", json.dumps(b["runtime_stamp"].get("library_versions")))
