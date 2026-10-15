#!/usr/bin/env python3
"""Read-only two-sided sha256 manifest for the A2 independent copy.

Walks the destination copy, maps each file back to the same relative path under
the owner's read-only source tree, hashes both sides and writes
<DST>/COPY-MANIFEST.tsv. Never modifies the source tree.

Status values:
  SAME       source and destination byte-identical (sha256 + size)
  DIFF       path exists on both sides but content differs  -> HARD STOP
  SELF_NEW   authored by lane A2, intentionally absent from source
  PRUNED_*   (listed separately) source file deliberately not copied

Exit code 1 if any DIFF is found.
"""
import hashlib
import os
import sys

SRC = '/data/group4/20261006-093203-codex-6385a841'
DST = '/data/group4/20261008-023143-qoder-d266d3a9/A2_sonicrep'

# Directories inside DST that are lane-A2 runtime/scratch, not part of the copy.
SKIP_PREFIXES = ('raw/', 'tmp/', 'cache/')
# Files lane A2 authored itself; expected to be absent from the source tree.
SELF = {'COPY-MANIFEST.tsv', 'FINDING.md', 'run_own.sh', 'a2_metrics.py',
        'A2-PRUNE-LIST.txt', 'A2-CLOSURE.txt', 'A2-IMPORT-PROBE.txt'}
# Source-only subtrees deliberately NOT copied (historical output / caches /
# quota-gate launchers). Reported for completeness, not hashed.
PRUNED = ['cache/', 'tmp/', 'uv-cache/', 'source-snapshots/', 'mujoco314-only/',
          'out/<all historical run directories except w7-source-binding, '
          'generated_phases2, w7-generated-text>',
          'wave1..wave7 *.tar.gz evidence packages',
          'wave*-summary.json / wave*-progress*.json / wave*-launches.jsonl',
          'wave*-write-probe.bin', '*.lock']


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    argv = sys.argv[1:]
    out_name = 'COPY-MANIFEST.tsv'
    skip = list(SKIP_PREFIXES)
    self_names = set(SELF)
    while argv:
        if argv[0] == '--out':
            out_name = argv[1]
            argv = argv[2:]
        elif argv[0] == '--skip-prefix':
            skip.append(argv[1])
            argv = argv[2:]
        elif argv[0] == '--self':
            self_names.add(argv[1])
            argv = argv[2:]
        else:
            print('unknown arg %s' % argv[0])
            return 2
    rows = []
    diff = 0
    selfnew = 0
    total = 0
    for root, dirs, files in os.walk(DST):
        dirs.sort()
        for name in sorted(files):
            dst = os.path.join(root, name)
            rel = os.path.relpath(dst, DST).replace(os.sep, '/')
            if rel.startswith(tuple(skip)):
                continue
            size = os.path.getsize(dst)
            total += size
            dsha = sha(dst)
            src = os.path.join(SRC, rel)
            if os.path.isfile(src):
                ssha = sha(src)
                status = 'SAME' if (ssha == dsha and os.path.getsize(src) == size) else 'DIFF'
                if status == 'DIFF':
                    diff += 1
            else:
                src = '<ABSENT_IN_SOURCE>'
                status = 'SELF_NEW' if os.path.basename(rel) in self_names else 'UNEXPECTED_NEW'
                if status == 'SELF_NEW':
                    selfnew += 1
                else:
                    diff += 1
            rows.append((src, dst, size, dsha, status))
    rows.sort(key=lambda r: r[1])
    out = os.path.join(DST, out_name)
    d = os.path.dirname(out)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# A2 independent-copy sha256 manifest (read-only on source)\n')
        f.write('# SRC=%s\n# DST=%s\n' % (SRC, DST))
        f.write('# SKIP_PREFIXES=%s\n' % ' '.join(skip))
        for p in PRUNED:
            f.write('# PRUNED_FROM_COPY: %s\n' % p)
        f.write('source_path\ttarget_path\tbytes\tsha256\tstatus\n')
        for r in rows:
            f.write('%s\t%s\t%d\t%s\t%s\n' % r)
    same = sum(1 for r in rows if r[4] == 'SAME')
    print('manifest=%s' % out)
    print('files=%d SAME=%d SELF_NEW=%d DIFF_or_UNEXPECTED=%d total_bytes=%d (%.1f MiB)'
          % (len(rows), same, selfnew, diff, total, total / 1048576.0))
    print('size_bound_4GiB=%s' % ('PASS' if total <= 4 * 1024**3 else 'FAIL'))
    return 1 if diff else 0


if __name__ == '__main__':
    sys.exit(main())
