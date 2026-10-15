#!/usr/bin/env python3
"""verify_repo.py — one-command self-check for this repo.

Usage
    python tools/verify_repo.py            # presence + size for every row, sha for a 400-row sample
    python tools/verify_repo.py --full     # sha256 for every row (~500 MB of reads)
    python tools/verify_repo.py --meshes DIR   # check a fetched Unitree G1 mesh folder against model-assets.json

Exit code 0 means every check passed; non-zero prints the failing lines. The tool is read-only:
it writes nothing, opens no sockets, and never runs a simulation.
"""
import glob, hashlib, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, "EXPORT-MANIFEST.tsv")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def say(sec, line):
    print("[%s] %s" % (sec, line))


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


full = "--full" in sys.argv
meshes = sys.argv[sys.argv.index("--meshes") + 1] if "--meshes" in sys.argv else None
fails = []

# 1. manifest vs working tree -------------------------------------------------
rows = [l.rstrip("\n").split("\t") for l in open(MAN, encoding="utf-8") if l.strip()]
say("manifest", "rows=%d (covers every tracked file except the manifest itself)" % len(rows))
missing = [f[0] for f in rows if not os.path.isfile(os.path.join(ROOT, f[0]))]
sizediff = [(f[0], f[1], os.path.getsize(os.path.join(ROOT, f[0]))) for f in rows
            if os.path.isfile(os.path.join(ROOT, f[0])) and os.path.getsize(os.path.join(ROOT, f[0])) != int(f[1])]
idx = [i for i, f in enumerate(rows) if f[0] != "EXPORT-MANIFEST.tsv"]
pick = idx if full else idx[::max(1, len(idx) // 400)][:400]
shadiff = []
for i in pick:
    p = os.path.join(ROOT, rows[i][0])
    if os.path.isfile(p) and sha256(p) != rows[i][3]:
        shadiff.append(rows[i][0])
for tag, seq in (("MISSING", missing), ("SIZEDIFF", sizediff), ("SHADIFF", shadiff)):
    for x in seq[:5]:
        say("manifest", "   %s %s" % (tag, x))
if missing or sizediff or shadiff:
    fails.append("manifest: missing=%d sizediffer=%d shadiffer=%d" % (len(missing), len(sizediff), len(shadiff)))
    say("manifest", "FAIL missing=%d sizediffer=%d shadiffer=%d (sha rows=%d)" %
        (len(missing), len(sizediff), len(shadiff), len(pick)))
else:
    say("manifest", "PASS missing=0 sizediffer=0 shadiffer=0 (sha checked %d/%d rows, mode=%s)" %
        (len(pick), len(rows), "full" if full else "sample"))

# 2. layout ------------------------------------------------------------------
groups = {}
for f in rows:
    parts = f[0].split("/")
    key = "/".join(parts[:2]) if len(parts) > 1 else "(repo root)"
    e = groups.setdefault(key, [0, 0, 0])
    e[0] += 1
    e[1] += int(f[1])
    if os.path.basename(f[0]).startswith(".flags"):
        e[2] += 1
for k in sorted(groups):
    n, b, fl = groups[k]
    say("layout", "%-46s %6d files %13d B  .flags*=%d" % (k, n, b, fl))

# 3. headline numbers --------------------------------------------------------
EXPECT = [
    ("experiments/cube35_wholehand_trial32/rep/out/normal_trial32/result.json", "success", True),
    ("experiments/cube35_wholehand_trial32/rep/out/normal_trial32/result.json", "max_lift_m", 0.12336126945999026),
    ("experiments/cube35_wholehand_trial32/rep/out/normal_trial32/result.json", "hold_min_lift_m", 0.08448322523549645),
    ("experiments/cube35_wholehand_trial32/rep/out/normal_trial32/result.json", "hold_slip_m", 0.0005198768604859854),
    ("experiments/cube35_wholehand_trial32/rep/out/normal_trial32/result.json", "simulation_steps", 56794),
    ("experiments/cube35_wholehand_trial32/rep/out/negative_trial32/result.json", "max_lift_m", 0.0008600741240607501),
    ("experiments/cube80_sideways_wholehand/out/side80_native3/result.json", "max_lift_m", 0.10857449062300661),
    ("experiments/cube80_sideways_wholehand/out/side80_native3/result.json", "hold_steps", 2500),
    ("experiments/cube80_sideways_wholehand/out/side80_native_negative3/result.json", "success", False),
    ("experiments/cube80_sideways_wholehand/out/side80_native_negative3/result.json", "max_lift_m", 0.001463928803046577),
    ("experiments/kimodo_closed_loop_best/harness_nat2/raw/wb_kimo_p6l1.result.json", "success", True),
    ("experiments/kimodo_closed_loop_best/harness_nat2/raw/wb_kimo_p6l1.result.json", "max_lift_m", 0.1439862432245319),
    ("experiments/kimodo_closed_loop_best/harness_nat2/raw/wb_kimo_p6l1.result.json", "hold_min_lift_m", 0.13118074148281422),
    ("experiments/kimodo_closed_loop_best/harness_nat2/raw/wb_kimo_p6l1.result.json", "gate_definition_version", 5),
]
bad = 0
for path, field, want in EXPECT:
    p = os.path.join(ROOT, path)
    if not os.path.isfile(p):
        fails.append("headline: missing file %s" % path)
        bad += 1
        continue
    got = json.load(open(p, encoding="utf-8", errors="replace")).get(field, "<absent>")
    if got != want:
        fails.append("headline: %s %s got=%r want=%r" % (path, field, got, want))
        bad += 1
say("headline", "%d field-level assertions, %d mismatched" % (len(EXPECT), bad))
if bad == 0:
    say("headline", "PASS all %d assertions match" % len(EXPECT))

# 4. gate sets and physics versions -----------------------------------------
gsizes, mvs, seen, paths = {}, {}, set(), []
for pat in ("**/result.json", "**/*.result.json"):
    for p in glob.glob(os.path.join(ROOT, pat), recursive=True):
        rp = rel(p)
        if rp.startswith("tools/") or rp in seen:
            continue
        seen.add(rp)
        paths.append(p)
for p in sorted(paths):
    try:
        d = json.load(open(p, encoding="utf-8", errors="replace"))
    except (ValueError, OSError):
        continue
    if not isinstance(d, dict):
        continue
    g = d.get("gates")
    if isinstance(g, dict):
        gsizes[len(g)] = gsizes.get(len(g), 0) + 1
    rs = d.get("runtime_stamp") if isinstance(d.get("runtime_stamp"), dict) else {}
    rt = d.get("runtime") if isinstance(d.get("runtime"), dict) else {}
    mv = rs.get("mujoco_version") or rs.get("mujoco") or rt.get("mujoco") or d.get("mujoco_version")
    mvs[str(mv or "(none)")] = mvs.get(str(mv or "(none)"), 0) + 1
say("gates", "result.json scanned=%d gate-count histogram=%s" % (len(paths), dict(sorted(gsizes.items()))))
say("gates", "mujoco version histogram=%s" % dict(sorted(mvs.items(), key=lambda kv: -kv[1])))
say("gates", "NOTE several gate-set sizes coexist -> they are not one yardstick; never merge them into one ranking")

# 5. W4 transfer arms --------------------------------------------------------
base = os.path.join(ROOT, "experiments", "w4_transfer_arms", "ws4_migrate")
if os.path.isdir(base):
    tc = tp = 0
    for arm in sorted(glob.glob(os.path.join(base, "rep_*"))):
        cells = glob.glob(os.path.join(arm, "rep", "out", "*", "result.json")) + \
            glob.glob(os.path.join(arm, "raw", "*.result.json"))
        npass = 0
        for p in cells:
            try:
                d = json.load(open(p, encoding="utf-8", errors="replace"))
            except (ValueError, OSError):
                continue
            g = d.get("gates")
            if d.get("success") is True and isinstance(g, dict) and g and all(g.values()):
                npass += 1
        tc += len(cells)
        tp += npass
        say("w4-arms", "%-16s cells=%3d pass=%3d .flags_flat=%s" % (
            os.path.basename(arm), len(cells), npass, os.path.isfile(os.path.join(arm, ".flags_flat"))))
    say("w4-arms", "TOTAL cells=%d all-gates-green=%d" % (tc, tp))

# 6. batch run ---------------------------------------------------------------
cdir = os.path.join(ROOT, "experiments", "batch_wholehand_360")
if os.path.isdir(cdir):
    s = json.load(open(os.path.join(cdir, "summary.json"), encoding="utf-8", errors="replace"))
    planned = {t["id"] for t in s["trials"]}
    have = {os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(cdir, "out", "*", "result.json"))}
    say("batch", "planned=%d present=%d absent=%s" % (len(planned), len(planned & have), sorted(planned - have)))
    say("batch", "recorded main_300=%s ablation_60=%s (values recorded at run time; recomputation from this repo"
        " can only reach the rows that exist here)" % (s["main_300_total"]["counts"], s["ablation_60_total"]["counts"]))
    if sha256(os.path.join(cdir, "manifest.json")) == s["manifest_sha256"]:
        say("batch", "PASS sha(manifest.json) == summary.manifest_sha256")
    else:
        fails.append("batch: manifest.json sha does not match the recorded value")

# 7. recorded-but-absent artefacts must all be registered --------------------
man_sha = {f[3] for f in rows}
HEX = re.compile(r"\b[0-9a-f]{64}\b")
want = set()
for f in rows:
    if f[0].endswith(".json") and int(f[1]) <= 8 * 1024 * 1024:
        p = os.path.join(ROOT, f[0])
        if os.path.isfile(p):
            want.update(HEX.findall(open(p, encoding="utf-8", errors="ignore").read()))
miss = want - man_sha
reg = set()
rf = os.path.join(ROOT, "ASSETS-MANIFEST.tsv")
if os.path.isfile(rf):
    for l in open(rf, encoding="utf-8"):
        fl = l.split("\t")
        if len(fl) >= 1 and len(fl[0]) == 64:
            reg.add(fl[0])
unreg = sorted(miss - reg)
say("deps", "sha values recorded in JSON=%d, bytes present here=%d, absent=%d, absent-and-registered=%d, unregistered=%d"
    % (len(want), len(want & man_sha), len(miss), len(miss & reg), len(unreg)))
if unreg:
    fails.append("deps: %d recorded sha values are neither in the repo nor in ASSETS-MANIFEST.tsv" % len(unreg))
else:
    say("deps", "PASS every recorded-but-absent artefact has a row in ASSETS-MANIFEST.tsv")

# 8. optional mesh check -----------------------------------------------------
mfile = os.path.join(ROOT, "experiments", "batch_wholehand_360", "model-assets.json")
if meshes:
    want = json.load(open(mfile, encoding="utf-8"))
    hit = diff = absent = 0
    for k, h in want.items():
        p = os.path.join(meshes, os.path.basename(k))
        if not os.path.isfile(p):
            absent += 1
        elif sha256(p) == h:
            hit += 1
        else:
            diff += 1
    say("assets", "mesh dir=%s MATCH=%d DIFFER=%d ABSENT=%d of %d" % (meshes, hit, diff, absent, len(want)))
    if hit != len(want):
        fails.append("assets: mesh bytes differ from those recorded at run time")
else:
    mdir = os.path.join(ROOT, "src", "sonic_v11_runtime", "src", "g1", "meshes")
    if os.path.isfile(mfile):
        want = json.load(open(mfile, encoding="utf-8"))
        hit = sum(1 for k, h in want.items()
                  if os.path.isfile(os.path.join(mdir, os.path.basename(k)))
                  and sha256(os.path.join(mdir, os.path.basename(k))) == h)
        say("assets", "in-repo meshes: %d/%d recorded hashes match src/sonic_v11_runtime/src/g1/meshes" % (hit, len(want)))
        if hit != len(want):
            fails.append("assets: in-repo meshes do not match the recorded hashes")
    else:
        say("assets", "no model-assets.json found; meshes dir present=%s" % os.path.isdir(mdir))

print()
if fails:
    print("VERDICT=FAIL  %d failing check(s)" % len(fails))
    for x in fails:
        print("   - " + x)
    sys.exit(1)
print("VERDICT=PASS  all checks passed (mode=%s)" % ("full" if full else "sample"))
