#!/usr/bin/env python3
"""W4c A/B aggregation: pair up <cell>__base / <cell>__phys and print one table.
Usage: ws4c_agg.py            -> all pairs present in rep_ext_phys/rep/out
       ws4c_agg.py b25_12_04  -> single pair
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ws4c_metrics import summarize  # noqa: E402

BASE = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_phys')
OUT = BASE / 'rep/out'
PROG = BASE / 'progress.txt'

wall = {}
for line in PROG.read_text().splitlines():
    p = line.split()
    if len(p) >= 3 and p[1].startswith('rc='):
        wall[p[0]] = dict(rc=p[1][3:], wall=p[2][5:])

cells = sys.argv[1:] or sorted({d.name.split('__')[0] for d in OUT.glob('*__*')})
rows = []
for cell in cells:
    for arm in ('base', 'phys'):
        d = OUT / f'{cell}__{arm}'
        if not (d / 'result.json').exists():
            rows.append(dict(cell=cell, arm=arm, missing=True))
            continue
        m = summarize(d)
        m['cell'] = cell
        m['arm'] = arm
        m['wall_s'] = wall.get(d.name, {}).get('wall')
        m['rc'] = wall.get(d.name, {}).get('rc')
        rows.append(m)

hdr = (f'{"cell":13s} {"arm":4s} {"wall":>5s} {"succ":5s} {"fail":26s} {"lift_mm":>8s} {"slip_mm":>8s} '
       f'{"redN":>4s} {"2pad/hold":>9s} {"runmax":>6s} {"lossEv":>6s} {"lossFr":>6s} {"air0":>5s} '
       f'{"padPen":>7s} {"padPenF":>7s} {"supPen":>7s} {"contactRows":>11s}')
print(hdr)
print('-' * len(hdr))
for m in rows:
    if m.get('missing'):
        print(f'{m["cell"]:13s} {m["arm"]:4s}   (not run yet)')
        continue
    print(f'{m["cell"]:13s} {m["arm"]:4s} {str(m["wall_s"]):>5s} {str(m["success"]):5s} '          f'{m["fail"][:26]:26s} {m["lift_mm"]:8.1f} {m["slip_mm"]:8.2f} {m["red_n"]:4d} '
          f'{str(m["two_pad_frames_in_hold"])+"/"+str(m["hold_frames"]):>9s} '
          f'{m["two_pad_run_max_0p01N"]:6d} {m["loss_events"]:6d} {m["loss_frames"]:6d} '
          f'{m["air_no_pad_frames"]:5d} {str(m["pad_pen_worst_mm"]):>7s} '
          f'{str((m["pad_pen_frame_stats"] or {}).get("frames_gt_0p5mm")):>7s} '
          f'{str(m["support_pen_worst_mm"]):>7s} {m["contact_rows"]:11d}')
print()
print('per-cell detail (json):')
print(json.dumps(rows, indent=1, default=str))
