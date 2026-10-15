#!/usr/bin/env python3
"""W4c renderer: replay a recorded cell (trajectory.npz + scene.xml) to mp4.
Own file; does not modify any other worker's renderer. Two-panel (full + hand) view.
Usage: ws4c_render.py <episode_dir> <out.mp4> [stride]
Needs: MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa LD_LIBRARY_PATH=<osmesa dir>
"""
import json, subprocess, sys
from pathlib import Path
import mujoco
import numpy as np

FFMPEG = Path('/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/'
              'imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2')

def main():
    ep = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    stride = int(sys.argv[3]) if len(sys.argv) > 3 else 4   # 25 Hz record -> 6.25 fps
    res = json.loads((ep / 'result.json').read_text())
    z = np.load(ep / 'trajectory.npz', allow_pickle=False)
    m = mujoco.MjModel.from_xml_path(str(ep / 'scene.xml'))
    d = mujoco.MjData(m)
    W, H = 480, 320
    r = mujoco.Renderer(m, height=H, width=W)
    full = mujoco.MjvCamera()
    full.type = mujoco.mjtCamera.mjCAMERA_FREE
    full.lookat[:] = [.1, 0., .8]; full.distance = 2.45
    full.azimuth = -115; full.elevation = -12
    hand = mujoco.MjvCamera()
    hand.type = mujoco.mjtCamera.mjCAMERA_FREE
    hand.lookat[:] = [.275, -.12, .82]; hand.distance = .55
    hand.azimuth = -125; hand.elevation = -15
    fps = 25. / stride
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(FFMPEG), '-v', 'error', '-nostdin', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{2*W}x{H}', '-r', f'{fps}', '-i', '-', '-an', '-c:v', 'libx264',
           '-threads', '2', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
           '-movflags', '+faststart', str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    phases = [str(x) for x in z['phase']]
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
    meta = dict(source=str(ep), success=res.get('success'), gates_red=[k for k, v in res['gates'].items() if not v],
                lift_mm=round((res.get('hold_min_lift_m') or -1) * 1000, 1),
                slip_mm=round((res.get('hold_slip_m') or -1) * 1000, 2),
                frames=int(len(z['qpos'])), stride=stride, fps=fps, panels=['full', 'hand'],
                physics_recipe_w4c=res.get('physics_recipe_w4c'),
                note='Recorded MuJoCo state replay for this task only; no dynamics re-integration, no claim change.')
    out.with_suffix('.json').write_text(json.dumps(meta, indent=1))
    print(f'rc={rc} -> {out} {out.stat().st_size} bytes  stderr_tail={err!r}' if rc == 0 else
          f'FAIL rc={rc} stderr={err!r}')
    return rc

sys.exit(main())
