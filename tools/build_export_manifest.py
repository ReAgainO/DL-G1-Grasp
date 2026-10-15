#!/usr/bin/env python3
"""build_export_manifest.py — regenerate EXPORT-MANIFEST.tsv from the working tree.

    python tools/build_export_manifest.py

Format: path \t bytes \t mtime \t sha256 \t class  (no header, no self-reference:
the manifest never contains its own hash). Run it twice if ASSETS-MANIFEST.tsv also changed,
so that the row for ASSETS-MANIFEST.tsv carries its final hash.
"""
import hashlib, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKIP = {".git", "__pycache__", ".qoder"}
MAN = os.path.join(ROOT, "EXPORT-MANIFEST.tsv")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


rows, skipped = [], 0
for dp, dns, fns in os.walk(ROOT):
    dns[:] = [d for d in dns if d not in SKIP]
    for fn in fns:
        p = os.path.join(dp, fn)
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        if rel == "EXPORT-MANIFEST.tsv":
            continue
        try:
            st = os.lstat(p)
            if os.path.islink(p) or not os.path.isfile(p):
                skipped += 1
                continue
            h = sha256(p)
        except OSError:
            skipped += 1
            continue
        top = rel.split("/")[0]
        cls = "data" if top in ("experiments", "src", "refs") else ("tool" if top == "tools" else "doc")
        rows.append([rel, str(st.st_size), str(int(st.st_mtime)), h, cls])
rows.sort()
open(MAN, "w", encoding="utf-8", newline="\n").write("".join("\t".join(r) + "\n" for r in rows))
print("[manifest] rows=%d bytes=%d skipped=%d" % (len(rows), sum(int(r[1]) for r in rows), skipped))
