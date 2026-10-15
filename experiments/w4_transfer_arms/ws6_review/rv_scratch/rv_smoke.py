#!/usr/bin/env python3
"""RV independent smoke comparator (does NOT use the workers' scripts).
Strict: reports keys only in A/B, shape/dtype mismatch, NaN-aware bitwise equality,
non-NaN equal, count of NaN positions. Works with allow_pickle=True for object arrays.
Usage: rv_smoke.py A_dir B_dir [label]
"""
import json, sys
import numpy as np
from pathlib import Path

def npz(p):
    p = Path(p)
    try:
        return np.load(p / 'trajectory.npz', allow_pickle=False)
    except ValueError:
        print('  [warn] npz requires pickle; falling back to allow_pickle=True (local trusted artifact)')
        return np.load(p / 'trajectory.npz', allow_pickle=True)

def res(p):
    return json.loads((Path(p) / 'result.json').read_text())

def cmp(label, A, B):
    print('=' * 90)
    print(label)
    print('  A =', A)
    print('  B =', B)
    za, zb = npz(A), npz(B)
    ka, kb = set(za.files), set(zb.files)
    print('  keys only in A:', sorted(ka - kb) or '-')
    print('  keys only in B:', sorted(kb - ka) or '-')
    bad = 0
    for k in sorted(ka & kb):
        x, y = za[k], zb[k]
        if x.shape != y.shape:
            print('   %-28s SHAPE %s vs %s  <-- MISMATCH' % (k, x.shape, y.shape)); bad += 1; continue
        if x.dtype != y.dtype:
            print('   %-28s DTYPE %s vs %s  <-- MISMATCH' % (k, x.dtype, y.dtype)); bad += 1; continue
        if x.dtype.kind == 'f':
            nan_a = int(np.isnan(x.astype(float)).sum()); nan_b = int(np.isnan(y.astype(float)).sum())
            m = ~(np.isnan(x.astype(float)) | np.isnan(y.astype(float)))
            idx = (~np.isnan(x.astype(float))) & (~np.isnan(y.astype(float)))
            both_nan = int((np.isnan(x.astype(float)) & np.isnan(y.astype(float))).sum())
            nonnan_eq = bool(np.array_equal(x.astype(float)[idx], y.astype(float)[idx]))
            d = float(np.max(np.abs(x.astype(float)[idx] - y.astype(float)[idx]))) if idx.any() else 0.0
            bit = bool(np.array_equal(x.astype(float), y.astype(float), equal_nan=True))
            if not bit: bad += 1
            print('   %-28s shape=%s nanA=%d nanB=%d both_nan=%d nonNaN_equal=%s max|d|(nonNaN)=%.3e bitwise(NaN==NaN)=%s'
                  % (k, x.shape, nan_a, nan_b, both_nan, nonnan_eq, d, bit))
        elif x.dtype.kind in 'iu':
            bit = bool(np.array_equal(x, y))
            if not bit: bad += 1
            print('   %-28s shape=%s bitwise=%s' % (k, x.shape, bit))
        else:
            same = list(map(str, x.ravel())) == list(map(str, y.ravel()))
            if not same: bad += 1
            print('   %-28s obj/non-numeric identical=%s (len %d)' % (k, same, x.size))
    ra, rb = res(A), res(B)
    print('  --- result.json headline')
    for k in ['success', 'legacy_success', 'fail_reason', 'hold_min_lift_m', 'hold_slip_m', 'max_lift_m', 'duration_s']:
        va, vb = ra.get(k), rb.get(k)
        print('   %-20s A=%s B=%s %s' % (k, va, vb, 'SAME' if va == vb else 'DIFF'))
    ga, gb = ra.get('gates') or {}, rb.get('gates') or {}
    print('   red_A=%s' % (sorted(k for k, v in ga.items() if not v),))
    print('   red_B=%s' % (sorted(k for k, v in gb.items() if not v),))
    print('   => ARRAYS %s' % ('ALL BITWISE EQUAL' if bad == 0 else 'HAVE %d DIFFERENCES' % bad))

if __name__ == '__main__':
    cmp(sys.argv[3] if len(sys.argv) > 3 else 'PAIR', sys.argv[1], sys.argv[2])
