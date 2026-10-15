#!/usr/bin/env python3
"""W4h W1S family survey: random-sample hand configs at the exact run() init pose and
classify the cube-in-cage relation (cube at cf = the ALIGN equilibrium seat).

Families (by pads' rel-z vs cube centre, mm):
  H  hood   : all three pads rel_z > +35   (fingers above the cube, pressing top face)
  C  cradle : all three pads rel_z < -35   (cube rests on the pads from below)
  M  clamp  : >=1 pad rel_z > +35 and >=1 pad rel_z < -35  (top-bottom straddle)
  X  mixed/side otherwise
Holdable = >=2 pads with sphere-box gap in [-1.8,-0.2]mm and the palm mesh clear (>0.3mm).
Read-only wrt arm sources; writes only ws4h/scratch.
Usage: ws4h_families.py EDGE [N] -> prints the top configs per family.
"""
import json, sys, time, warnings
import numpy as np, mujoco
from pathlib import Path
warnings.filterwarnings('ignore')
M = Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
sys.path.insert(0, str(M / 'ws4h'))
from ws4h_seat import Rig, gap_box, band, hinge, PADS

EDGE = float(sys.argv[1]) if len(sys.argv) > 1 else 80.
NS = int(sys.argv[2]) if len(sys.argv) > 2 else 12000

def main():
    t0 = time.time()
    rig = Rig(EDGE)
    lo = rig.m.jnt_range[rig.hj, 0] + 1e-6
    hi = rig.m.jnt_range[rig.hj, 1] - 1e-6
    v5c = np.array([0.42, -0.2, -0.8, 1.7, 0.05, 1.7, 0.05])
    rng = np.random.RandomState(11)
    rows = []
    n_eval = 0
    for i in range(NS):
        if i % 3 == 0:
            q = lo + (hi - lo) * rng.rand(7)
        else:
            q = np.clip(v5c + rng.normal(0, .45, 7), lo, hi)
        try:
            r = rig.probe_qc(q)
        except Exception:
            continue
        n_eval += 1
        g = np.array(r['gap']); rz = np.array([x[2] for x in r['rel']]) * 1e3
        nband = int(((g >= -.0018) & (g <= -.0002)).sum())
        fam = 'H' if (rz > 35).all() else 'C' if (rz < -35).all() else 'M' if ((rz > 35).any() and (rz < -35).any()) else 'X'
        c = 400 * band(g[0] * 1e3, -1.8, -0.2) + 400 * band(g[1] * 1e3, -1.8, -0.2) + 200 * band(g[2] * 1e3, -1.8, 0.4)
        c += 500 * hinge(0.3 - r['palm'] * 1e3) + 200 * hinge(-1.5 - r['segmin'] * 1e3) + 20 * hinge(20 - r['span'] * 1e3)
        if nband >= 2: c -= 5000 * nband
        rows.append((c, fam, nband, q, g, rz, r['palm'] * 1e3, r['span'] * 1e3, r['segmin'] * 1e3, r['cf']))
    print('eval=%d/%d wall=%.1fs' % (n_eval, NS, time.time() - t0))
    from collections import Counter
    cnt = Counter((r[1], r[2] >= 2) for r in rows)
    print('family x holdable(>=2pad in band):', dict(cnt))
    for fam in 'HCMX':
        sub = sorted([r for r in rows if r[1] == fam and r[2] >= 2], key=lambda r: r[0])[:4]
        print('--- family %s: %d holdable samples' % (fam, sum(1 for r in rows if r[1] == fam and r[2] >= 2)))
        for c, f, nb, q, g, rz, pm, sp, sm, cf in sub:
            print('   c=%.0f pads_in_band=%d q=%s gap_mm=%s relz_mm=%s palm=%.1fmm span=%.1fmm seg=%.1fmm cf=%s' % (
                c, nb, np.round(q, 3).tolist(), np.round(g * 1e3, 2).tolist(), np.round(rz, 1).tolist(), pm, sp, sm, np.round(cf, 4).tolist()))
    # also: best over all regardless of family band count
    print('--- global top by band-count then cost:')
    for c, f, nb, q, g, rz, pm, sp, sm, cf in sorted(rows, key=lambda r: (-r[2], r[0]))[:8]:
        print('   nb=%d fam=%s c=%.0f q=%s gap_mm=%s relz_mm=%s palm=%.1f span=%.1f seg=%.1f' % (
            nb, f, c, np.round(q, 3).tolist(), np.round(g * 1e3, 2).tolist(), np.round(rz, 1).tolist(), pm, sp, sm))

if __name__ == '__main__':
    main()
