#!/usr/bin/env python3
"""fixE stratum tally: read rep_fixE results newer than a cutoff and summarize.
Owner task 20261008-182000-qoder-7d11d1ae."""
import collections, json, os, sys
from pathlib import Path

BASE = Path("/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_cfg")
CUT = float(sys.argv[1]) if len(sys.argv) > 1 else 0.  # mtime epoch cutoff (0 = all)
rows = []
for p in sorted((BASE / 'rep/out').glob('*/result.json')):
    st = p.stat()
    if st.st_mtime < CUT:
        continue
    r = json.loads(p.read_text())
    n = p.parent.name
    red = sorted(k for k, v in r['gates'].items() if not v)
    rows.append(dict(name=n, success=bool(r.get('success')), fail=r.get('fail_reason') or '',
                     lift=round((r.get('hold_min_lift_m') or -1) * 1000, 1),
                     slip=round((r.get('hold_slip_m') or -1) * 1000, 2),
                     red=red, red_n=len(red)))
succ = [x for x in rows if x['success']]
print(f'fixE stratum (mtime>{CUT}): total={len(rows)} success={len(succ)}')
for x in succ:
    print('  SUCCESS', x['name'], 'lift=', x['lift'], 'slip=', x['slip'])
nil = [x for x in rows if not x['success'] and not x['fail']]
tmo = [x for x in rows if x['fail'] == 'approach native branch settling timeout']
other = [x for x in rows if not x['success'] and x['fail'] and x['fail'] != 'approach native branch settling timeout']
print(f'  fail=None(ran all phases)={len(nil)}  still-approach-timeout={len(tmo)}  other-fail={len(other)}')
tally = collections.Counter()
for x in nil:
    for g in x['red']:
        tally[g] += 1
print('  red-gate tally for ran-all-phases:')
for k, v in tally.most_common():
    print(f'    {k}: {v}')
print('  near-success (<=2 red gates):')
for x in sorted(nil, key=lambda y: y['red_n'])[:15]:
    if x['red_n'] <= 2:
        print(f"    {x['name']}: lift={x['lift']} slip={x['slip']} red={x['red']}")
for x in other:
    print(f"  other: {x['name']} fail={x['fail']} red_n={x['red_n']}")
print('  per-cell CSV ->', BASE / 'fixE_tally.csv')
with open(BASE / 'fixE_tally.csv', 'w') as f:
    f.write('name,success,fail,lift_mm,slip_mm,red_n,red\n')
    for x in rows:
        f.write(f"{x['name']},{x['success']},{x['fail']},{x['lift']},{x['slip']},{x['red_n']},{'|'.join(x['red'])}\n")
