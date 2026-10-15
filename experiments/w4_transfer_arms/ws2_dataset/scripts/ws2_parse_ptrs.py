#!/usr/bin/env python3
"""Parse git cat-file --batch output of LFS pointers -> manifest (episode, sha256, size)."""
import re
import sys

raw = open("/tmp/ws2_ptrs.txt", encoding="utf-8", errors="replace").read()

# Each record: "<gitsha> blob <ptrsize>\n<content>\n\n" or "<path> missing\n"
blocks = re.split(r"\n(?=[0-9a-f]{40} blob |HEAD:|[0-9a-f]{40} commit )", raw)
manifest = []
for b in blocks:
    m = re.match(r"[0-9a-f]{40} blob \d+\n", b)
    if not m:
        continue
    oid = re.search(r"oid sha256:([0-9a-f]{64})", b)
    size = re.search(r"size (\d+)", b)
    if oid and size:
        manifest.append((oid.group(1), int(size.group(1))))

print("pointers parsed:", len(manifest))
tot = sum(s for _, s in manifest)
print("total parquet bytes: %d = %.1f MB" % (tot, tot / 1e6))
sizes = [s for _, s in manifest]
if sizes:
    print("min/max/avg MB: %.2f / %.2f / %.2f" % (min(sizes) / 1e6, max(sizes) / 1e6, (tot / len(sizes)) / 1e6))

# expected manifest: episode index -> (sha256, size). Only first 118 records are the parquet files
with open("/tmp/ws2_parquet_manifest.txt", "w") as f:
    for i, (sha, sz) in enumerate(manifest[:118]):
        f.write("%06d %s %d\n" % (i, sha, sz))
print("manifest written: /tmp/ws2_parquet_manifest.txt")
