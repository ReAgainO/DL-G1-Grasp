#!/usr/bin/env python3
"""W4e kick-off forensics: cube displacement timeline for b25_12_04 across arms.
Usage: ws4e_kick.py <tag> <cell_dir> [<tag> <cell_dir> ...]
Reads telemetry.csv.gz only (read-only)."""
import gzip, sys
from pathlib import Path
import numpy as np

def tel(p):
    with gzip.open(p, 'rt') as f:
        f.readline()
        cols = f.readline().lstrip('# ').strip().split(',')
        arr = np.loadtxt(f, delimiter=',')
    return {c: arr[:, i] for i, c in enumerate(cols)}

args = sys.argv[1:]
pairs = [(args[i], args[i + 1]) for i in range(0, len(args), 2)]
for tag, d in pairs:
    t = tel(Path(d) / 'telemetry.csv.gz')
    ts = t['time_s']; cx = t['cube_x_m']; cy = t['cube_y_m']; cz = t['cube_z_m']
    loaded = ((t['thumb_force_N'] > .01).astype(int) + (t['index_force_N'] > .01).astype(int)
              + (t['middle_force_N'] > .01).astype(int))
    two = np.where(loaded >= 2)[0]
    first = float(ts[two[0]]) if len(two) else None
    dxy = np.hypot(cx - cx[0], cy - cy[0])
    print(f'{tag}: n={len(ts)} t_end={ts[-1]:.2f}s first_two_pad_s={first} '
          f'max|dxy|={dxy.max()*1000:.1f}mm max_z={(cz.max()-cz[0])*1000:.1f}mm z_end={(cz[-1]-cz[0])*1000:.1f}mm')
    row = []
    for tt in (5, 10, 15, 20, 30, 45):
        i = int(np.argmin(np.abs(ts - tt)))
        row.append(f't={ts[i]:5.2f} dxy={np.hypot(cx[i]-cx[0],cy[i]-cy[0])*1000:6.2f} z={((cz[i]-cz[0])*1000):6.2f} 2pad={int(loaded[i])}')
    print('   ' + ' | '.join(row))
