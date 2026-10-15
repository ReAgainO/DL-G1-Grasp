#!/usr/bin/env python3
"""Kimodo (G1Skeleton34, 30 fps) -> official SONIC harness motion contract.

The official harness consumes motions through ``motion_input.ArdyMotion``:
a 25 fps NPZ holding ``local_rot_mats (T,34,3,3)``, ``root_positions (T,3)``,
``posed_joints (T,34,3)``, ``fps`` and ``text``, plus an optional paired CSV
that must agree with the harness's own conversion to <=1e-6.

This script resamples a Kimodo clip onto the harness clock and emits both
files.  The CSV is produced by calling the harness's *own* ``convert()``, so
the parity check is structurally exact rather than fitted.

It must run with the harness rep directory on sys.path, e.g.
    cd <rep> && python -c ...
Usage:
    kimo2harness.py --npz IN.npz --stem OUT/stem --text "..." [--fps 25]
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import motion_input as mi  # noqa: E402


# ---------------------------------------------------------------- rotations
def mat_to_quat(R):
    """Rotation matrix -> unit quaternion (w, x, y, z)."""
    R = np.asarray(R, dtype=np.float64)
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2.0
        q = np.array([0.25 * s, (R[2, 1] - R[1, 2]) / s,
                      (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s])
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2.0
        q = np.array([(R[2, 1] - R[1, 2]) / s, 0.25 * s,
                      (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s])
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2.0
        q = np.array([(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s,
                      0.25 * s, (R[1, 2] + R[2, 1]) / s])
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2.0
        q = np.array([(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s,
                      (R[1, 2] + R[2, 1]) / s, 0.25 * s])
    return q / np.linalg.norm(q)


def quat_to_mat(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def slerp(a, b, t):
    d = float(np.dot(a, b))
    if d < 0.0:
        b, d = -b, -d
    if d > 1.0 - 1e-12:
        q = (1 - t) * a + t * b
    else:
        ang = np.arccos(np.clip(d, -1.0, 1.0))
        q = (np.sin((1 - t) * ang) * a + np.sin(t * ang) * b) / np.sin(ang)
    return q / np.linalg.norm(q)


def orthonormalize(R):
    u, _, vt = np.linalg.svd(R)
    out = u @ vt
    if np.linalg.det(out) < 0:
        u[:, -1] *= -1
        out = u @ vt
    return out


# ---------------------------------------------------------------- resampling
def resample_rot_mats(mats, fps_in, fps_out):
    """Slerp a (T, B, 3, 3) stack from fps_in onto the fps_out clock."""
    T, B = mats.shape[0], mats.shape[1]
    T_out = int(round((T - 1) * fps_out / fps_in)) + 1
    x = (np.arange(T_out) / fps_out) * fps_in
    i = np.clip(x.astype(int), 0, T - 1)
    j = np.minimum(i + 1, T - 1)
    u = x - i
    quats = np.empty((T, B, 4))
    for f in range(T):
        for b in range(B):
            quats[f, b] = mat_to_quat(mats[f, b])
    out = np.empty((T_out, B, 3, 3), dtype=np.float64)
    for k in range(T_out):
        for b in range(B):
            out[k, b] = orthonormalize(quat_to_mat(slerp(quats[i[k], b], quats[j[k], b], u[k])))
    return out


def resample_vec(arr, fps_in, fps_out):
    T = arr.shape[0]
    T_out = int(round((T - 1) * fps_out / fps_in)) + 1
    x = (np.arange(T_out) / fps_out) * fps_in
    i = np.clip(x.astype(int), 0, T - 1)
    j = np.minimum(i + 1, T - 1)
    u = (x - i).reshape((-1,) + (1,) * (arr.ndim - 1))
    return (1 - u) * arr[i] + u * arr[j]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True, help="Kimodo native output npz (30 fps)")
    ap.add_argument("--stem", required=True, help="output stem, e.g. <rep>/src/original_motions/kimo_reach")
    ap.add_argument("--text", default=None, help="prompt text (defaults to the npz 'text' field)")
    ap.add_argument("--fps", type=float, default=25.0, help="harness clock (must be 25)")
    ap.add_argument("--pin-root", action="store_true",
                    help="force root_positions to the SONIC anchor [0,0,0.7887]")
    a = ap.parse_args()

    z = np.load(a.npz, allow_pickle=True)
    lrm = np.asarray(z["local_rot_mats"], dtype=np.float64)
    root = np.asarray(z["root_positions"], dtype=np.float64)
    posed = np.asarray(z["posed_joints"], dtype=np.float64)
    fps_in = float(z["fps"]) if "fps" in z.files else 30.0
    text = a.text or (str(z["text"]) if "text" in z.files else "")

    print("in  :", a.npz)
    print("   frames=%d fps=%g bones=%d" % (lrm.shape[0], fps_in, lrm.shape[1]))
    if a.pin_root:
        root = np.tile(np.array([0.0, 0.0, 0.7887]), (root.shape[0], 1))

    lrm_r = resample_rot_mats(lrm, fps_in, a.fps)
    root_r = resample_vec(root, fps_in, a.fps)
    posed_r = resample_vec(posed, fps_in, a.fps)
    n = lrm_r.shape[0]
    print("out : frames=%d fps=%g" % (n, a.fps))

    lrm32 = lrm_r.astype(np.float32)
    root32 = root_r.astype(np.float32)
    posed32 = posed_r.astype(np.float32)

    stem = Path(a.stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    npz_out = stem.with_suffix(".npz")
    csv_out = stem.with_suffix(".csv")
    if npz_out.exists() or csv_out.exists():
        raise SystemExit("refuse to overwrite existing %s" % npz_out)

    np.savez_compressed(
        npz_out,
        local_rot_mats=lrm32,
        root_positions=root32,
        posed_joints=posed32,
        fps=np.array(a.fps, dtype=np.int64),
        text=np.array(text),
    )

    # Paired CSV via the harness's own converter -> parity is exact by construction.
    summary = json.loads((HERE / "src/original_motions/summary.json").read_text())
    q, names = mi.convert({"root_positions": root32, "local_rot_mats": lrm32},
                          summary["bone_names"], HERE / "src/ardy_converter_g1.xml")
    np.savetxt(csv_out, q, delimiter=",", fmt="%.9g")
    print("wrote:", npz_out, npz_out.stat().st_size, "bytes")
    print("wrote:", csv_out, csv_out.stat().st_size, "bytes")

    # Hard verification through the harness's own loader.
    m = mi.ArdyMotion(npz_out, check_csv=csv_out)
    au = m.audit
    print("VERIFY ArdyMotion OK  parity joint=%.3e root=%.3e rot=%.3e"
          % (au["parity_joint_max_rad"], au["parity_root_translation_max_m"],
             au["parity_rotation_matrix_max"]))
    print("   native_frames=%d duration=%.3fs last_sample=%.3fs"
          % (au["native_frames"], au["native_clip_duration_s"], au["last_sample_time_s"]))

    # Geometry sanity: right-arm travel and wrist height excursion.
    qa = m.qpos
    arm = qa[:, 29:36]
    print("   right-arm joint travel (rad):", np.round(arm.max(0) - arm.min(0), 3).tolist())
    print("   root xyz range:", np.round(qa[:, :3].min(0), 4).tolist(),
          np.round(qa[:, :3].max(0), 4).tolist())
    jl = {}
    for k, nm in enumerate(names[:29]):
        jl[nm] = None
    print("   joint_names[0:5]:", names[:5])


if __name__ == "__main__":
    main()
