#!/usr/bin/env python3
"""W4e three-way aggregator: for each experiment cell read result.json of the arms
and print a comparison table.  Reads only files under ws4_migrate/ (own work root).

Arms:
  base  = rep_base/rep/out/<cell>            (W4a local baseline; fallback=0 cells are
                                               bitwise S1000-equivalent per W4a_DESIGN.md)
  pd    = rep_ext_pd/rep/out/<cell>          (W4b2 arm, read-only reference)
  phys  = rep_ext_phys/rep/out/<cell>__phys  (W4c arm, read-only reference; N/A where absent)
  comb  = rep_ext_comb/rep/out/<cell>__comb  (this experiment)

S1000-only baselines (b25_00_14, a35_00_06/10/15) were never rerun locally; their
values live in W4b2_PD.md §3 (transcribed from the read-only S1000 lane) and are
marked "doc" here.
"""
import json, sys
from pathlib import Path

M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
CELLS = [('b25_02_06', 25), ('b25_00_10', 25), ('b25_00_14', 25), ('b25_00_00', 25),
         ('a35_00_06', 35), ('a35_00_10', 35), ('a35_00_15', 35)]

def read(rj):
    try:
        r = json.loads(Path(rj).read_text())
    except Exception:
        return None
    g = r.get('gates', {})
    return dict(
        success=bool(r.get('success')),
        fail=r.get('fail_reason') or '',
        lift=round((r.get('hold_min_lift_m') if r.get('hold_min_lift_m') is not None else -1) * 1000, 1),
        slip=round((r.get('hold_slip_m') if r.get('hold_slip_m') is not None else -1) * 1000, 2),
        red_n=sum(1 for v in g.values() if not v),
        red=[k for k, v in g.items() if not v],
        fb=(r.get('reference_filter') or {}).get('certified_continuation_steps'),
    )

def fmt(tag, d, note=''):
    if d is None:
        return f'{tag}: N/A {note}'
    s = 'T' if d['success'] else 'F'
    reds = ','.join(d['red'][:3]) + ('…' if len(d['red']) > 3 else '')
    fb = '' if d.get('fb') in (0, None) else f" fb={d['fb']}"
    return f"{tag}: {s} lift={d['lift']} slip={d['slip']} red_n={d['red_n']} [{reds}]{fb} {d['fail']}{note}"

print('== three-way table (one block per cell) ==')
for cell, edge in CELLS:
    b = read(M / 'rep_base/rep/out' / cell / 'result.json') if edge == 25 and cell != 'b25_00_14' else None
    p = read(M / 'rep_ext_pd/rep/out' / cell / 'result.json')
    h = read(M / 'rep_ext_phys/rep/out' / f'{cell}__phys' / 'result.json')
    c = read(M / 'rep_ext_comb/rep/out' / f'{cell}__comb' / 'result.json')
    print(f'[{cell}] edge={edge}mm')
    for tag, d in (('base', b), ('pd  ', p), ('phys', h), ('comb', c)):
        print('  ' + fmt(tag, d))
print()
print('== machine-readable ==')
for cell, edge in CELLS:
    out = dict(cell=cell, edge=edge)
    out['base'] = read(M / 'rep_base/rep/out' / cell / 'result.json') if edge == 25 and cell != 'b25_00_14' else None
    out['pd'] = read(M / 'rep_ext_pd/rep/out' / cell / 'result.json')
    out['phys'] = read(M / 'rep_ext_phys/rep/out' / f'{cell}__phys' / 'result.json')
    out['comb'] = read(M / 'rep_ext_comb/rep/out' / f'{cell}__comb' / 'result.json')
    print(json.dumps(out, default=str))
