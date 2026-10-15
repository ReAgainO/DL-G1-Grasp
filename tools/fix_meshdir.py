#!/usr/bin/env python3
"""fix_meshdir.py — point MJCF meshdir entries at the in-repo mesh copy.

The 79 recorded MJCF files reference meshes by absolute paths from the machine they ran on,
e.g.  meshdir="/data/group4/.../g1/meshes".  The same mesh bytes now live in this repo at
src/sonic_v11_runtime/src/g1/meshes (50 of them sha-verified against model-assets.json).

Usage:
    python tools/fix_meshdir.py            # dry run: list what would change + old/new file sha
    python tools/fix_meshdir.py --write    # apply

Note: rewriting a scene changes its bytes, so it will no longer be byte-identical to the
runtime_stamp.model_sha recorded for the original run. That is expected for a rerun; the
original files stay untouched unless --write is given, and the old hash is printed either way.
"""
import hashlib, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESHDIR = os.path.join(ROOT, "src", "sonic_v11_runtime", "src", "g1", "meshes")
PAT = re.compile(r'meshdir="[^"]*g1/meshes"')

write = "--write" in sys.argv
changed = 0
for dp, dns, fns in os.walk(ROOT):
    if ".git" in dp:
        continue
    for fn in fns:
        if not fn.endswith(".xml"):
            continue
        p = os.path.join(dp, fn)
        s = open(p, encoding="utf-8", errors="replace").read()
        if "g1/meshes" not in s:
            continue
        new = PAT.sub('meshdir="%s"' % MESHDIR.replace("\\", "/"), s)
        if new == s:
            continue
        old_sha = hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()
        new_sha = hashlib.sha256(new.encode("utf-8", "replace")).hexdigest()
        changed += 1
        rel = os.path.relpath(p, ROOT)
        print("%s  %s -> %s" % (rel, old_sha[:12], new_sha[:12]))
        if write:
            open(p, "w", encoding="utf-8", newline="").write(new)
print("files with foreign meshdir: %d  (%s)" % (changed, "WRITTEN" if write else "dry run, use --write to apply"))
