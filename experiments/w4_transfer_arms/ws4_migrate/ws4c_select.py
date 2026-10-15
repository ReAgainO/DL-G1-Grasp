#!/usr/bin/env python3
"""ws4c: choose representative 20mm failure cells from the READ-ONLY S1000 record.
Read-only. Ranking rule (reported in W4c_PHYS.md):
  primary  = deepest attempt (max_lift_m), then (max simultaneous loaded pads, longest 2-pad dwell)
  filter   = reference_filter.certified_continuation_steps == 0  (fallback=0, so the
             rep_base reference stream is identical to the S1000 stream)
"""
import gzip, json, sys
from pathlib import Path
import numpy as np

S = Path('/data/group4/20261008-125638-qoder-d266d3a9/S1000')
JOBS = S / 'jobs.txt'
OUT = S / 'rep/out'

jobs = {}
for line in JOBS.read_text().splitlines():
    p = line.split('|')
    if len(p) >= 6:
        jobs[p[0]] = dict(edge=p[1], cx=p[2], cy=p[3], face=p[4], stem=p[5])

def load(name):
    return json.loads((OUT / name / 'result.json').read_text())

def telemetry_pad_stats(name):
    """max simultaneous pads with normal force > .05 N; longest run with >=2 pads."""
    path = OUT / name / 'telemetry.csv.gz'
    if not path.exists():
        return None
    with gzip.open(path, 'rt') as f:
        head = f.readline()  # stamp
        cols = f.readline().lstrip('# ').strip().split(',')
        arr = np.loadtxt(f, delimiter=',')
    idx = [cols.index(c) for c in ('thumb_force_N', 'index_force_N', 'middle_force_N')]
    f_pads = arr[:, idx]
    loaded = (f_pads > .05).sum(axis=1)
    two = loaded >= 2
    best_run = 0
    run = 0
    for v in two:
        run = run + 1 if v else 0
        best_run = max(best_run, run)
    return dict(max_pads=int(loaded.max()), two_pad_steps=int(two.sum()),
                longest_two_pad_run=int(best_run), n_steps=int(len(arr)),
                max_pad_force_N=float(f_pads.max()))

rows = []
layers = sys.argv[1:] or ['c20d', 'c20f']
for name, j in sorted(jobs.items()):
    if name.split('_')[0] not in layers:
        continue
    if not (OUT / name / 'result.json').exists():
        continue
    r = load(name)
    rf = r.get('reference_filter') or {}
    red = sorted(k for k, v in r['gates'].items() if not v)
    rows.append(dict(
        name=name, cx=j['cx'], cy=j['cy'], face=j['face'], stem=j['stem'],
        max_lift=round((r.get('max_lift_m') or 0) * 1000, 2),
        hold_lift=round((r.get('hold_min_lift_m') or -1) * 1000, 1),
        slip=round((r.get('hold_slip_m') or -1) * 1000, 2),
        red_n=len(red), fail=r.get('fail_reason') or '',
        fallback=int(rf.get('certified_continuation_steps') or 0),
        contact_rows=(r.get('contact_audit_summary') or {}).get('raw_contact_rows'),
        duration=round(float(r.get('duration_s') or 0), 1)))

print('layers', layers, 'n_cells', len(rows))
for layer in layers:
    sub = [x for x in rows if x['name'].startswith(layer)]
    print(f'\n=== {layer}: n={len(sub)} max_lift_mm min/med/max = '
          f'{min(x["max_lift"] for x in sub)}/{np.median([x["max_lift"] for x in sub])}/'
          f'{max(x["max_lift"] for x in sub)}; fallback=0 count={sum(1 for x in sub if x["fallback"]==0)}')

rank = [x for x in rows if x['fallback'] == 0]
rank.sort(key=lambda x: -x['max_lift'])
print('\n--- top 14 by max_lift among fallback=0 (pad stats from telemetry):')
for x in rank[:14]:
    st = telemetry_pad_stats(x['name'])
    x.update(st or {})
    print(f'{x["name"]:12s} cx={x["cx"]} cy={x["cy"]} face={x["face"]} '
          f'max_lift={x["max_lift"]:8.2f} hold_lift={x["hold_lift"]:7.1f} slip={x["slip"]:8.2f} '
          f'red_n={x["red_n"]} max_pads={x.get("max_pads")} two_pads_steps={x.get("two_pad_steps")} '
          f'run={x.get("longest_two_pad_run")} maxF={x.get("max_pad_force_N")} '
          f'rows={x["contact_rows"]} dur={x["duration"]} fail={x["fail"][:28]}')
print('\n--- fallback distribution over the two layers:',
      {k: sum(1 for x in rows if x['fallback'] == k) for k in (0, 1, 2, 3, 4)})
