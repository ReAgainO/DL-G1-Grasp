#!/usr/bin/env python3
"""W4c final summary: emit the markdown tables for W4c_PHYS.md (all arms found on disk).
Adds the contact-continuity proxy n_2pad_runs (number of >=1-frame two-pad contact stretches
over the whole run; a chatter/continuity indicator) on top of ws4c_metrics.summarize().
"""
import gzip, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ws4c_metrics import summarize, runs  # noqa: E402

ROOT = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/rep_ext_phys')
OUT = ROOT / 'rep/out'
PROG = ROOT / 'progress.txt'
WALL = {}
for line in PROG.read_text().splitlines():
    p = line.split()
    if len(p) >= 3 and p[1].startswith('rc='):
        WALL[p[0]] = (p[1][3:], p[2][5:])

def chatter(ep):
    with gzip.open(ep / 'telemetry.csv.gz', 'rt') as f:
        f.readline(); cols = f.readline().lstrip('# ').strip().split(',')
        a = np.loadtxt(f, delimiter=',')
    ix = [cols.index(k) for k in ('thumb_force_N', 'index_force_N', 'middle_force_N')]
    f_pads = a[:, ix]
    n = (f_pads > .01).sum(axis=1)
    r = runs(n >= 2)
    r10 = runs((f_pads > .1).sum(axis=1) >= 2)
    return dict(runs_0p01N=len([1 for _, L in r if L >= 1]),
                runs_ge25_0p01N=len([1 for _, L in r if L >= 25]),
                runs_ge25_0p1N=len([1 for _, L in r10 if L >= 25]),
                longest_gap_between_2pad=int(max(np.diff([s for s, L in r if L >= 25]), default=0)))

def row(cell, arm):
    d = OUT / f'{cell}__{arm}'
    if not (d / 'result.json').exists():
        return None
    m = summarize(d)
    q = m['hold_contact_quality']
    c = chatter(d)
    rc, wall = WALL.get(d.name, ('?', '?'))
    return dict(cell=cell, arm=arm, wall=wall, rc=rc, succ=m['success'], fail=m['fail'], red=m['red'],
                lift=m['lift_mm'], slip=m['slip_mm'], maxlift=m['max_lift_mm'],
                two=f'{m["two_pad_frames_in_hold"]}/{m["hold_frames"]}',
                summin=q['sum_pad_min_N'], second=q['second_pad_min_N'],
                padpen=m['pad_pen_worst_mm'], pen05=(m['pad_pen_frame_stats'] or {}).get('frames_gt_0p5mm'),
                suppen=m['support_pen_worst_mm'], loss=m['loss_events'], air0=m['air_no_pad_frames'],
                dur=m['duration_s'], **c)

groups = {'25mm': ['b25_00_00', 'b25_04_01', 'b25_12_04', 'b25_02_06', 'b25_00_10', 'b25_10_17'],
          '20mm': ['c20d_10_03', 'c20d_12_03', 'c20f_09_01', 'c20f_06_19'],
          'ablation': ['b25_00_00', 'b25_12_04', 'c20d_10_03']}
arms = {'25mm': ['base', 'phys'], '20mm': ['base', 'phys'], 'ablation': ['base', 'soft', 'sub4', 'phys', 'phys2']}
for g, cells in groups.items():
    print(f'\n===== {g} =====')
    print('| cell | arm | wall_s | success | red gates | hold lift mm | slip mm | 2pad/HOLD | sumF_min N | padPen mm | pen>0.5mm frames | 2pad stretches (>=25f) | fail |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for cell in cells:
        for arm in arms[g]:
            r = row(cell, arm)
            if r is None:
                continue
            print(f"| {r['cell']} | {r['arm']} | {r['wall']} | {r['succ']} | {len(r['red'])} {','.join(r['red']) or '-'} | "
                  f"{r['lift']} | {r['slip']} | {r['two']} | {r['summin']} | {r['padpen']} | {r['pen05']} | "
                  f"{r['runs_ge25_0p01N']} (all {r['runs_0p01N']}) | {r['fail'] or '-'} |")
