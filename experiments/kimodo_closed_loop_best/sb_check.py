#!/usr/bin/env python3
"""Check a 36-column Kimodo/ARDY qpos CSV against the G1 MuJoCo joint contract.

Prefers the sonic-bridge official loader; falls back to a direct range check.

Usage: sb_check.py <csv> <fps> [<csv> <fps> ...]
"""
import sys
from pathlib import Path
import numpy as np
import mujoco

SB = Path("/home/group4/group4_dasc7606c/repos/sonic-bridge")
XML = SB / "g1/g1_29dof_with_hand.xml"

sys.path.insert(0, str(SB))
official = None
try:
    from motion_adapter.kimodo_loader import load_kimodo_csv  # noqa: E402
    official = load_kimodo_csv
except Exception as exc:  # pragma: no cover
    print("[info] official loader unavailable: %r" % (exc,))

m = mujoco.MjModel.from_xml_path(str(XML))
hinge = [j for j in range(m.njnt) if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE]
names = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j) for j in hinge]
lo = np.array([m.jnt_range[j, 0] for j in hinge])
hi = np.array([m.jnt_range[j, 1] for j in hinge])
print("model %s hinges=%d" % (XML.name, len(hinge)))

for path, fps_s in zip(sys.argv[1::2], sys.argv[2::2]):
    fps = float(fps_s)
    a = np.loadtxt(path, delimiter=",")
    if a.ndim == 1:
        a = a[None]
    print("\n== %s  rows=%d cols=%d fps=%.1f" % (Path(path).name, len(a), a.shape[1], fps))
    if a.shape[1] != 36:
        print("   !! not 36 columns")
        continue
    if official is not None:
        try:
            tr = official(path, fps, model_xml_path=XML)
            print("   official kimodo_loader: ACCEPTED  frames=%d" % len(tr.timestamps))
        except Exception as exc:
            print("   official kimodo_loader: REJECTED -> %s" % (exc,))
    j = a[:, 7:36]
    excess = np.maximum(np.maximum(lo[None] - j, j - hi[None]), 0.0)
    worst = np.unravel_index(int(np.argmax(excess)), excess.shape)
    print("   worst excess %.4f rad at frame %d joint %s (value %.4f, range [%.4f,%.4f])"
          % (excess[worst], worst[0], names[worst[1]], j[worst], lo[worst[1]], hi[worst[1]]))
    for k in range(20, 29):
        v = j[:, k]
        nb = int(((v < lo[k] - 1e-9) | (v > hi[k] + 1e-9)).sum())
        if nb:
            print("   %-28s [%7.3f,%7.3f] range[%7.3f,%7.3f] out=%d/%d"
                  % (names[k], v.min(), v.max(), lo[k], hi[k], nb, len(v)))
