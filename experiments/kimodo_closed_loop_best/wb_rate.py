import json, glob, os

B = "/data/group4/20261008-232029-workbuddy-34e89f61/harness_s1000/rep/out"
rows = []

for d in sorted(glob.glob(B + "/wb_*")):
    n = os.path.basename(d)
    f = os.path.join(d, "result.json")
    if not os.path.exists(f):
        rows.append((n, None, None, None, None, None))
        continue
    r = json.load(open(f))
    g = r.get("gates", {}) or {}
    ok = sum(1 for v in g.values() if v)
    tot = len(g)
    failed = [k for k, v in g.items() if not v]
    rows.append((n, r.get("success"), str(ok) + "/" + str(tot), r.get("max_lift_m"), failed, r.get("source", "")))

print("cell             succ    gates    max_lift_m  failed_gates")
print("-" * 100)
for n, s, gt, lift, failed, src in rows:
    if s is None:
        print("%-16s %-7s %-8s %-11s %s" % (n, "-", "-", "-", "NO_RESULT"))
        continue
    lv = "%.5f" % lift if isinstance(lift, float) else str(lift)
    print("%-16s %-7s %-8s %-11s %s" % (n, str(s), gt, lv, failed))

print()
print("=== KIMODO-only cells (source contains kimodo) ===")
kim = [r for r in rows if r[5] and "kimodo" in str(r[5]).lower()]
for n, s, gt, lift, failed, src in kim:
    print("%-16s succ=%s gates=%s src=%s" % (n, s, gt, src))

print()
print("=== finished cells summary ===")
fin = [r for r in rows if r[1] is not None]
ok = [r for r in fin if r[1] is True]
print("finished=%d  success_true=%d  success_false=%d" % (len(fin), len(ok), len(fin) - len(ok)))

print()
print("=== source field of every finished cell ===")
for n, s, gt, lift, failed, src in fin:
    print("%-16s %s" % (n, src))
