#!/usr/bin/env python3
"""W4g ENV 35mm focused refinement (v5d): coordinate descent around the fist family
with a 35mm-specific cost: thumb pad gap in [-2.5, 0], middle pad gap <= -0.2 (engaged),
index pad gap in [-3, +3], distal meshes in [-3, +1.5], palm in [-2, +6], table >= +2mm.
Prints top-6 with full readout. Read-only wrt rep_ext_env.
"""
import sys, warnings
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, '/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate/ws4g')
import ws4g_envsearch2 as es

def cost35(rig, q5, s):
    c, r = rig.cost(q5, s)   # base cost keeps meshes/palm/table/wrist in the picture
    g = [es.gap_box(r['relp'][i], s) for i in range(3)]
    def win(v, lo, hi, w):
        e = max(lo - v, 0., v - hi)
        return w * e * e * 1e6
    c += win(g[0], -.0025, 0., 60.)
    c += win(g[2], -.0025, -.0002, 60.)
    c += win(g[1], -.003, .003, 25.)
    c += max(0., .002 - r['dtable']) ** 2 * 400. * 1e6
    return c, r

def main():
    rig = es.Rig(35)
    s = .0175
    seeds = [
        [0.42, -0.2, -0.8, 1.7, 0.05],
        [0.45, -0.25, -0.95, 1.75, 0.1],
        [0.40, -0.15, -0.7, 1.75, 0.15],
        [0.42, -0.25, -0.9, 1.8, 0.1],
        [0.38, -0.2, -0.85, 1.72, 0.05],
    ]
    best = []
    for q0 in seeds:
        q = np.clip(np.array(q0, float), es.LO, es.HI)
        c, _ = cost35(rig, q, s)
        for st in (0.12, 0.05, 0.02):
            improved = True
            guard = 0
            while improved and guard < 80:
                improved = False
                guard += 1
                for k in range(5):
                    for dv in (st, -st):
                        q2 = q.copy()
                        q2[k] = min(max(q2[k] + dv, es.LO[k]), es.HI[k])
                        c2, _ = cost35(rig, q2, s)
                        if c2 < c - 1e-9:
                            q, c = q2, c2
                            improved = True
        best.append((c, q.copy()))
    best.sort(key=lambda x: x[0])
    print('===== 35mm v5d tops =====')
    for c, q in best[:6]:
        _, r = cost35(rig, q, s)
        qh = rig.q7(q)
        print('cost=%.1f q=%s' % (c, [round(float(x), 4) for x in qh]))
        print('   span=%.1f n=%s D(mm) t2=%+.1f i1=%+.1f m1=%+.1f palm=%+.1f guard=%+.1f table=%+.1f' % (
            r['L'] * 1e3, np.round(r['n'], 3).tolist(), r['D'][es.SEG[0]] * 1e3, r['D'][es.SEG[1]] * 1e3,
            r['D'][es.SEG[2]] * 1e3, r['dpalm'] * 1e3, r['dguard'] * 1e3, r['dtable'] * 1e3))
        print('   pad gaps(mm)=%s wrist_rel=%s' % ([round(es.gap_box(r['relp'][i], s) * 1e3, 2) for i in range(3)],
              [round(float(x) * 1e3, 1) for x in r['wrist_rel']]))
    print('DONE')

if __name__ == '__main__':
    main()
