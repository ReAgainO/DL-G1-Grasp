#!/usr/bin/env python3
"""ws4a: S1000 (d266d3a9) 25mm/20mm layer failure statistics. READ-ONLY over d266d3a9.

Runs on worker00039. Writes nothing to the read-only source; prints a report.
Usage: python ws4a_agg.py
"""
import json
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path('/data/group4/20261008-125638-qoder-d266d3a9/S1000/rep/out')
GROUPS = [('b25', 'b25_'), ('c20d', 'c20d_'), ('c20f', 'c20f_')]


def classify(r):
    if r.get('success'):
        return 'SUCCESS'
    fail = r.get('fail_reason') or ''
    if not fail:
        red = set(k for k, v in r.get('gates', {}).items() if not v)
        if 'hold_7cm' in red and 'slip_1cm' in red:
            return 'RAN-all: lift+slip red'
        if 'hold_7cm' in red:
            return 'RAN-all: no-lift red'
        if 'slip_1cm' in red:
            return 'RAN-all: slip red'
        if 'two_fingers' in red:
            return 'RAN-all: two_fingers red'
        return 'RAN-all: other red=' + '|'.join(sorted(red))[:70]
    if fail == 'approach native branch settling timeout':
        return 'TIMEOUT: branch settling'
    if fail.startswith('approach transition timeout') or fail.startswith('approach actual wrist clearance timeout'):
        return 'TIMEOUT: approach clearance/transition'
    if fail.startswith('alignment timeout'):
        return 'TIMEOUT: alignment'
    if fail.startswith('two-finger contact timeout'):
        return 'TIMEOUT: close two-finger contact'
    if fail.startswith('contact-qualified table-return timeout'):
        return 'TIMEOUT: setdown return'
    if 'horizon exhausted' in fail:
        return 'HORIZON: 90s'
    if fail.startswith('fall/nonfinite'):
        return 'FALL: nonfinite/base'
    if fail.startswith('reference feasibility stop'):
        return 'STOP: reference feasibility'
    if fail.startswith('native branch static search rejected'):
        return 'STOP: native branch static'
    return 'OTHER: ' + fail[:60]


def fmt_stat(vals):
    vals = [float(v) for v in vals if v is not None and v == v]
    if not vals:
        return 'n/a'
    return 'min=%.4f med=%.4f max=%.4f' % (min(vals), st.median(vals), max(vals))


def main():
    for name, pref in GROUPS:
        cells = {}
        for p in sorted(ROOT.glob(pref + '*/result.json')):
            try:
                cells[p.parent.name] = json.loads(p.read_text())
            except Exception as e:
                print('LOADFAIL', p, e)
        n = len(cells)
        print('=== layer %s: n=%d ===' % (name, n))
        succ = [c for c in cells.values() if c.get('success')]
        print('success=%d (%.1f%%)' % (len(succ), 100.0 * len(succ) / max(n, 1)))
        fr = Counter((c.get('fail_reason') or 'NONE(ran all phases)') for c in cells.values())
        print('fail_reason distribution:')
        for k, v in fr.most_common():
            print('   %6.1f%%  n=%3d  %s' % (100.0 * v / max(n, 1), v, k[:110]))
        cls = Counter(classify(c) for c in cells.values())
        print('merged classes:')
        for k, v in cls.most_common():
            print('   %6.1f%%  n=%3d  %s' % (100.0 * v / max(n, 1), v, k))
        rg = Counter()
        for c in cells.values():
            for k, v in c.get('gates', {}).items():
                if not v:
                    rg[k] += 1
        print('red gate histogram (all %d cells):' % n)
        for k, v in rg.most_common():
            print('   %6.1f%%  n=%3d  %s' % (100.0 * v / max(n, 1), v, k))
        for clsname in sorted(set(classify(c) for c in cells.values())):
            sel = [c for c in cells.values() if classify(c) == clsname]
            lifts = [c.get('hold_min_lift_m') for c in sel]
            slips = [c.get('hold_slip_m') for c in sel]
            print('  [%s] n=%d  hold_min_lift_m: %s' % (clsname, len(sel), fmt_stat(lifts)))
            print('       hold_slip_m: %s' % fmt_stat(slips))
        ran = [c for c in cells.values() if not c.get('success') and not c.get('fail_reason')]
        rn = Counter(sum(1 for v in c['gates'].values() if not v) for c in ran)
        print('ran-all(n=%d) red_n dist: %s' % (len(ran), dict(sorted(rn.items()))))
        fb = [nm for nm, c in cells.items() if ((c.get('reference_filter') or {}).get('certified_continuation_steps') or 0) > 0]
        print('ref_filter certified_continuation_steps>0: n=%d  %s' % (len(fb), fb[:10]))
        clip = [nm for nm, c in cells.items() if (c.get('correction_clipped_cells') or 0) > 0]
        print('correction_clipped_cells>0: n=%d' % len(clip))
        mt = Counter(round(float((c.get('reference_filter') or {}).get('max_plan_horizon_s') or 0.0), 1) for c in cells.values())
        print('max_plan_horizon_s histogram: %s' % dict(sorted(mt.items())))
        if name == 'b25':
            print('per-cell b25 listing (name success fail lift_mm slip_mm red):')
            for nm in sorted(cells):
                c = cells[nm]
                red = [k for k, v in c.get('gates', {}).items() if not v]
                print('   %s %s fail=%s lift=%.1f slip=%.2f red=%s' % (
                    nm, c.get('success'), (c.get('fail_reason') or '-')[:48],
                    (c.get('hold_min_lift_m') or -9) * 1000, (c.get('hold_slip_m') or -9) * 1000, red))
        print()


if __name__ == '__main__':
    main()
