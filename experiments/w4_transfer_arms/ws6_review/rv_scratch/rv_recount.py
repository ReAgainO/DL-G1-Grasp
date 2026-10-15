#!/usr/bin/env python3
"""RV independent recount: recompute success/lift/slip/gates straight from result.json.
READ-ONLY over audited dirs. No writes outside stdout.
"""
import json, sys, glob, os, statistics as st
from pathlib import Path

B = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
SRC = Path('/data/group4/20261008-125638-qoder-d266d3a9/S1000/rep/out')

RED_GATES = None  # computed per record from gates dict

def load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception as e:
        return {'__loadfail__': str(e)}

def row(cell, d):
    if '__loadfail__' in d:
        return dict(cell=cell, loadfail=d['__loadfail__'])
    g = d.get('gates') or {}
    red = sorted([k for k, v in g.items() if not v])
    return dict(
        cell=cell,
        success=bool(d.get('success')),
        legacy_success=bool(d.get('legacy_success')),
        n_gates=len(g),
        red=red,
        fail_reason=(d.get('fail_reason') or '')[:70],
        max_lift=d.get('max_lift_m'),
        hold_min_lift=d.get('hold_min_lift_m'),
        slip=d.get('hold_slip_m'),
        min_contact=d.get('hold_min_contact_bodies'),
        reason=(d.get('fail_reason') or 'RANALL')[:40],
    )

def scan(root, pattern):
    out = {}
    for p in sorted(Path(root).glob(pattern)):
        if p.is_dir() and (p / 'result.json').exists():
            out[p.name] = row(p.name, load(p / 'result.json'))
    return out

def brief(r):
    if 'loadfail' in r:
        return '%s LOADFAIL %s' % (r['cell'], r['loadfail'])
    return '%-14s succ=%-5s legacy=%-5s lift=%s hmin=%s slip=%s red=%s fr=%s' % (
        r['cell'], r['success'], r['legacy_success'],
        _f(r['max_lift']), _f(r['hold_min_lift']), _f(r['slip']),
        ','.join(r['red']) if r['red'] else '-', r['fail_reason'][:38])

def _f(v):
    return 'n/a' if v is None else '%.4f' % float(v)

def section(title):
    print('\n' + '=' * 78)
    print(title)
    print('=' * 78)

# ---------------- W4a ----------------
section('W4a  baseline  rep_base/rep/out/b25_*  (5 cells)')
base = scan(B / 'rep_base/rep/out', 'b25_*')
for c in sorted(base):
    print(' ', brief(base[c]))
ns = sum(1 for r in base.values() if r.get('success'))
nl = sum(1 for r in base.values() if r.get('legacy_success'))
print('  => n=%d success=%d legacy_success=%d' % (len(base), ns, nl))
print('  anchor e35n_00_06 exists:', (B / 'rep_base/rep/out/e35n_00_06/result.json').exists())

section('W4a  vs S1000 source d266d3a9 (same cells)')
for c in sorted(base):
    sp = SRC / c / 'result.json'
    if not sp.exists():
        cand = glob.glob(str(SRC / ('*' + c + '*') / 'result.json'))
        print('  %-12s SRC-MISSING direct; glob=%s' % (c, cand[:3]))
        continue
    s = row(c, load(sp))
    b = base[c]
    same_succ = (bool(s['success']) == bool(b['success']))
    same_red = (s['red'] == b['red'])
    print('  %-12s src_succ=%-5s base_succ=%-5s same=%s | src_red=%s base_red=%s same_red=%s' % (
        c, s['success'], b['success'], same_succ, s['red'], b['red'], same_red))
    print('               src lift=%s hmin=%s slip=%s || base lift=%s hmin=%s slip=%s' % (
        _f(s['max_lift']), _f(s['hold_min_lift']), _f(s['slip']),
        _f(b['max_lift']), _f(b['hold_min_lift']), _f(b['slip'])))

# ---------------- W4b ----------------
section('W4b  rep_ext_cfg/rep/out/b25_*  (12 cells)')
cfg = scan(B / 'rep_ext_cfg/rep/out', 'b25_*')
for c in sorted(cfg):
    print(' ', brief(cfg[c]))
ns = sum(1 for r in cfg.values() if r.get('success'))
print('  => n=%d success=%d legacy_success=%d' % (len(cfg), ns,
      sum(1 for r in cfg.values() if r.get('legacy_success'))))
print('  --- delta vs rep_base same cell ---')
shared = sorted(set(base) & set(cfg))
worse = same = better = 0
for c in shared:
    b, x = base[c], cfg[c]
    bv, xv = b['hold_min_lift'], x['hold_min_lift']
    tag = 'SAME'
    if b.get('success') and not x.get('success'):
        tag = 'DEGRADED'
    elif xv is not None and bv is not None:
        d = xv - bv
        if d < -0.005:
            tag = 'WORSE(hminkg %.3f)' % d
        elif d > 0.005:
            tag = 'BETTER(hminkg +%.3f)' % d
    if tag == 'DEGRADED': worse += 1
    print('  %-12s %-24s base_hmin=%s cfg_hmin=%s base_succ=%s cfg_succ=%s' % (
        c, tag, _f(bv), _f(xv), b['success'], x['success']))
print('  degradation (base success -> cfg fail): %d' % worse)

# ---------------- W4b2 ----------------
section('W4b2  rep_ext_pd/rep/out  (b25 + a35)')
pd = scan(B / 'rep_ext_pd/rep/out', '*')
for c in sorted(pd):
    print(' ', brief(pd[c]))

# ---------------- W4c ----------------
section('W4c  rep_ext_phys/rep/out/<cell>__<arm>  (27 arms)')
phys = scan(B / 'rep_ext_phys/rep/out', '*')
cells = {}
for name in sorted(phys):
    if '__' not in name:
        print('  NON-ARM dir:', name, phys[name].get('success'))
        continue
    cell, arm = name.rsplit('__', 1)
    cells.setdefault(cell, {})[arm] = phys[name]
arms_seen = sorted({a for v in cells.values() for a in v})
print('  arms seen:', arms_seen)
tot = sum(len(v) for v in cells.values())
print('  => n_arms_total=%d (dirs=%d)' % (tot, len(phys)))
for cell in sorted(cells):
    for arm in sorted(cells[cell]):
        r = cells[cell][arm]
        print('  %-12s %-6s %s' % (cell, arm, brief(r).split(None, 1)[1]))

def denom(prefix):
    return {c: v for c, v in cells.items() if c.startswith(prefix)}
for label, pref in (('25mm(b25)', 'b25_'), ('20mm(c20)', 'c20')):
    grp = denom(pref)
    print('\n  -- %s : %d cells with any arm --' % (label, len(grp)))
    for arm in arms_seen:
        got = {c: v[arm] for c, v in grp.items() if arm in v}
        if not got:
            continue
        succ = sum(1 for r in got.values() if r.get('success'))
        print('     arm=%-6s n=%d success=%d  %s' % (
            arm, len(got), succ,
            ' '.join('%s=%s' % (c, 'S' if r['success'] else 'x') for c, r in sorted(got.items()))))
