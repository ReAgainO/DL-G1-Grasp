#!/usr/bin/env python3
"""RV independent recompute of W4c contact metrics (own code, caliber taken from W4c_PHYS.md §5).
LOADED pad = pad-cube normal force > 0.01 N ; 2pad/HOLD = HOLD-window frames with >=2 loaded pads.
Usage: rv_w4c_metrics.py <cell_dir> [...]
"""
import gzip, json, sys
from pathlib import Path
import numpy as np

def tele(p):
    with gzip.open(p, 'rt') as f:
        f.readline()
        cols = f.readline().lstrip('# ').strip().split(',')
        arr = np.loadtxt(f, delimiter=',')
    return {c: arr[:, i] for i, c in enumerate(cols)}

def contacts(p):
    with gzip.open(p, 'rt') as f:
        cols = None
        for line in f:
            s = line.lstrip('# ').strip()
            if s.startswith('time_s,'):
                cols = s.split(','); break
    idx = {k: cols.index(k) for k in ('time_s', 'category', 'distance_m', 'contact_fn_N')}
    arr = np.loadtxt(gzip.open(p, 'rt'), delimiter=',', usecols=tuple(idx.values()), skiprows=1 + sum(1 for _ in gzip.open(p, 'rt') if _.startswith('#')))
    return {k: arr[:, i] for i, k in enumerate(idx)}

def main(d):
    d = Path(d)
    r = json.loads((d / 'result.json').read_text())
    t = tele(d / 'telemetry.csv.gz')
    z = np.load(d / 'trajectory.npz', allow_pickle=False)
    ph = [str(x) for x in z['phase']]
    hold = [i for i, p in enumerate(ph) if p == 'HOLD']
    f = np.vstack([t['thumb_force_N'], t['index_force_N'], t['middle_force_N']]).T
    loaded = (f > 0.01).sum(axis=1)
    if hold:
        w = (t['time_s'] >= float(z['time'][hold[0]])) & (t['time_s'] <= float(z['time'][hold[-1]]))
    else:
        w = np.zeros(len(t['time_s']), bool)
    n2 = int((w & (loaded >= 2)).sum())
    holdn = int(w.sum())
    summin = float(f[w].sum(axis=1).min()) if holdn else None
    return dict(cell=d.name, success=bool(r['success']),
                red_n=sum(1 for v in r['gates'].values() if not v),
                lift_mm=round((r['hold_min_lift_m'] or -1) * 1000, 1),
                slip_mm=round((r['hold_slip_m'] or -1) * 1000, 2),
                two_pad_in_hold="%d/%d" % (n2, holdn),
                sum_pad_min_N=None if summin is None else round(summin, 4))

if __name__ == '__main__':
    for c in sys.argv[1:]:
        try:
            print(json.dumps(main(c), default=str))
        except Exception as e:
            print(json.dumps({'cell': c, 'error': '%s: %s' % (type(e).__name__, e)}))
