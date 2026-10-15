#!/usr/bin/env python3
"""W4c bitwise comparator: two trajectory.npz (or two cell dirs) + result.json scalars.
Usage: ws4c_cmp.py <cellA_dir_or_npz> <cellB_dir_or_npz> [--keys qpos,hand_reference,...]
"""
import json, sys
from pathlib import Path
import numpy as np

NPZ_SKIP = ('scene', 'runtime_stamp')

def load(p):
    p = Path(p)
    if p.is_dir():
        npz = p / 'trajectory.npz'
        res = json.loads((p / 'result.json').read_text())
        return npz, res
    return p, None

def main():
    a, b = sys.argv[1], sys.argv[2]
    npzA, resA = load(a)
    npzB, resB = load(b)
    # both npz files are produced by our own runs in this task (numeric/unicode only)
    za, zb = np.load(npzA, allow_pickle=False), np.load(npzB, allow_pickle=False)
    keys = [k for k in za.files if k in zb.files and k not in NPZ_SKIP]
    print(f'A = {npzA}\nB = {npzB}')
    allok = True
    for k in keys:
        va, vb = za[k], zb[k]
        if va.shape != vb.shape:
            print(f'  {k:22s} SHAPE MISMATCH {va.shape} vs {vb.shape}')
            allok = False
            continue
        if va.ndim == 0 or va.dtype.kind not in 'fiu':
            print(f'  {k:22s} (scalar/non-numeric) {va!r} vs {vb!r} {"OK" if str(va) == str(vb) else "DIFF"}')
            allok &= str(va) == str(vb)
            continue
        if va.dtype.kind in 'fiu' and vb.dtype.kind in 'fiu':
            d = np.nanmax(np.abs(va.astype(float) - vb.astype(float))) if va.size else 0.
            # equal_nan: unused NaN placeholders (e.g. wrist_target) must count as equal
            bit = bool(np.array_equal(va, vb, equal_nan=True))
            print(f'  {k:22s} shape={va.shape} bitwise={bit} max|d|={d:.3e}')
            allok &= bit
        else:
            same = all(list(map(str, va)) == list(map(str, vb)))
            print(f'  {k:22s} (non-numeric) identical={same}')
    if resA and resB:
        for k in ['success', 'fail_reason', 'hold_min_lift_m', 'hold_slip_m', 'max_lift_m', 'duration_s']:
            va, vb = resA.get(k), resB.get(k)
            print(f'  result.{k:20s} {va} vs {vb} {"OK" if va == vb else "DIFF"}')
        ga, gb = resA['gates'], resB['gates']
        diff = [k for k in set(ga) | set(gb) if ga.get(k) != gb.get(k)]
        print(f'  gates identical={not diff} diff={diff}')
    print('ALL ARRAY KEYS BITWISE EQUAL' if allok else 'ARRAY DIFFERENCES PRESENT')

main()
