#!/usr/bin/env python3
"""W4i renderer (own file; does not modify ws4c_render.py): replay a recorded cell
(trajectory.npz + scene.xml) to mp4 with the hand camera aimed at the ACTUAL preset seat
of this cell (ws4c's camera was tuned for the 80mm b25 seat). Two panels (full + hand).
Usage: ws4i_render.py <episode_dir> <out.mp4> [stride]
Needs: MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa LD_LIBRARY_PATH=<osmesa dir>
"""
import hashlib, json, subprocess, sys
from pathlib import Path
import mujoco
import numpy as np

FFMPEG = Path('/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/'
              'imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2')

def main():
    ep = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    stride = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    res = json.loads((ep / 'result.json').read_text())
    z = np.load(ep / 'trajectory.npz', allow_pickle=False)
    m = mujoco.MjModel.from_xml_path(str(ep / 'scene.xml'))
    d = mujoco.MjData(m)
    cube_b = m.body('red_cube').id
    cq = int(m.jnt_qposadr[int(m.body('red_cube').jntadr[0])])
    W, H = 480, 320
    r = mujoco.Renderer(m, height=H, width=W)
    full = mujoco.MjvCamera()
    full.type = mujoco.mjtCamera.mjCAMERA_FREE
    hand = mujoco.MjvCamera()
    hand.type = mujoco.mjtCamera.mjCAMERA_FREE
    fps = 25. / stride
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(FFMPEG), '-v', 'error', '-nostdin', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{2*W}x{H}', '-r', f'{fps}', '-i', '-', '-an', '-c:v', 'libx264',
           '-threads', '2', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
           '-movflags', '+faststart', str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    seat = np.asarray(res.get('w4h_preset_seat', {}).get('cube_pos_seat_m', [.275, -.12, .82]), float)
    full.lookat[:] = [seat[0], seat[1], .80]; full.distance = 2.2; full.azimuth = -115; full.elevation = -12
    hand.lookat[:] = seat + np.array([.015, .0, -.005]); hand.distance = .5; hand.azimuth = -125; hand.elevation = -15
    try:
        for k in range(0, len(z['qpos']), stride):
            d.qpos[:] = z['qpos'][k]
            d.qvel[:] = z['qvel'][k]
            mujoco.mj_forward(m, d)
            panels = []
            for cam in (full, hand):
                r.update_scene(d, camera=cam)
                panels.append(r.render().copy())
            proc.stdin.write(np.concatenate(panels, axis=1).tobytes())
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        err = proc.stderr.read().decode()[-800:]
        rc = proc.wait(timeout=60)
        r.close()
    rs = str(z['runtime_stamp']) if 'runtime_stamp' in z else ''
    meta = dict(source=str(ep), success=res.get('success'),
                gates_red=[k for k, v in res['gates'].items() if not v], n_red=sum(1 for v in res['gates'].values() if not v),
                lift_mm=round((res.get('max_lift_m') or -1) * 1000, 1),
                slip_mm=(round(res.get('hold_slip_m') * 1000, 2) if (res.get('hold_slip_m') or 1e9) < 1e8 else None),
                phases=[(e['phase'], round(e['time_s'], 3)) for e in res.get('events', [])],
                frames=int(len(z['qpos'])), stride=stride, fps=fps, panels=['full', 'hand'],
                camera_hand_lookat=seat.tolist(),
                runtime_stamp_sha256=hashlib.sha256(rs.encode()).hexdigest() if rs else None,
                runtime_stamp=json.loads(rs) if rs else None,
                note='W4i mechanism replay of a recorded MuJoCo state (no re-integration). This cell is NOT a 45-gate success; it is the best 50mm-class cell (pads carry into LIFT/HOLD). Labelled variant, W4i.')
    out.with_suffix('.json').write_text(json.dumps(meta, indent=1, default=str) + '\n')
    print(f'rc={rc} -> {out} {out.stat().st_size} bytes  stderr_tail={err!r}' if rc == 0 else
          f'FAIL rc={rc} stderr={err!r}')
    return rc

sys.exit(main())
