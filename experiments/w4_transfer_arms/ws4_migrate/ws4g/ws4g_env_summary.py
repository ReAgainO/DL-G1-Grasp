#!/usr/bin/env python3
"""W4g ENV summary: per-cell success/fail/lift/slip/red-gates + injection/level evidence.
Usage: ws4g_env_summary.py  -> stdout (caller redirects to ws4g_env_summary.out)
"""
import json, gzip
from pathlib import Path

BASE = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_env')
CFG = 0
rows = []
for p in sorted((BASE / 'rep/out').glob('*/result.json')):
    n = p.parent.name
    r = json.loads(p.read_text())
    red = sorted(k for k, v in r.get('gates', {}).items() if not v)
    g = r.get('grip_target_json') or {}
    e = r.get('envelope_collision') or {}
    en = e.get('enabled_geoms') or []
    rows.append((n, bool(r.get('success')), r.get('fail_reason') or '', r.get('hold_min_lift_m'), r.get('hold_slip_m'), red, g, e.get('level'), len(en), r.get('duration_s')))
print('cells=%d' % len(rows))
for (n, ok, fail, lift, slip, red, g, lvl, nen, dur) in rows:
    print('%-18s ok=%s fail=%-58s lift=%s slip=%s red=%s applied=%s lvl=%s ngeom=%s dur=%s' % (
        n, ok, fail[:58], None if lift is None else round(lift * 1000, 1), None if slip is None else round(slip * 1000, 2),
        ','.join(red) if red else '-', g.get('applied'), lvl, nen, None if dur is None else round(dur, 1)))
print()
print('== raw stdout evidence ==')
for n, *_ in rows:
    log = BASE / 'raw' / ('%s.stdout.log' % n)
    if not log.exists():
        continue
    txt = log.read_text(errors='replace')
    gline = [l for l in txt.splitlines() if l.startswith('GRIP_TARGET_JSON')][:1]
    eline = [l for l in txt.splitlines() if l.startswith('ENV_COLLISION')][:1]
    print('--', n)
    for l in gline:
        print('   ', l[:220])
    for l in eline:
        print('   ', l[:220])
