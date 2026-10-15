#!/usr/bin/env python3
"""Zero-physics replay renderer (TASKID 20261009-132809-qoder-9b946d7f).

Reads ONLY the recorded poses of an already-finished episode (qpos + phase) and writes
an MP4 by kinematic reconstruction (mj_forward, no mj_step): zero integration, no new
experiment, no gate/threshold change, source trees are read-only.

Usage: q2_video.py <episode_name>
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import mujoco

SRC = Path('/data/group4/20261008-202654-codex-182c4568/rep/out')          # read-only
OUT = Path('/data/group4/20261009-132809-qoder-9b946d7f/videos')
FFMPEG = Path('/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/'
              'imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2')
W, H = 960, 720
OUT_FPS = 12.5
STRIDE = 2
CAM = 'grasp_camera'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def fmt(t):
    m, s = divmod(t, 60)
    return f'00:{int(m):02d}:{s:06.3f}'


def main():
    name = sys.argv[1]
    ep = SRC / name
    assert ep.is_dir(), ep
    res = json.loads((ep / 'result.json').read_text())
    assert res['success'] is True, f'{name}: not success'
    assert all(res['gates'].values()), f'{name}: gates not all true'
    # trial32 stores its version in result.json['runtime']['mujoco'] (no runtime_stamp key);
    # the earlier w7 recipe used runtime_stamp.mujoco_version. Accept either, never render
    # with an interpreter that differs from the one that produced the numbers.
    rt = res.get('runtime') or {}
    src_mujoco = rt.get('mujoco') or res.get('runtime_stamp', {}).get('mujoco_version')
    assert src_mujoco == mujoco.__version__, (src_mujoco, mujoco.__version__)

    z = np.load(ep / 'trajectory.npz', allow_pickle=False)
    q, ph = z['qpos'], z['phase']
    fps_src = int(z['fps'])
    assert fps_src == 25 and STRIDE == 2
    idx = np.arange(0, len(q), STRIDE)

    m = mujoco.MjModel.from_xml_path(str(ep / 'scene.xml'))
    d = mujoco.MjData(m)
    assert m.nq == q.shape[1], (m.nq, q.shape[1])

    vid = OUT / f'{name}.mp4'
    assert FFMPEG.is_file(), FFMPEG
    cmd = [str(FFMPEG), '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(OUT_FPS), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'veryfast',
           '-crf', '20', '-pix_fmt', 'yuv420p', str(vid)]
    logf = open(OUT / f'{name}.ffmpeg.log', 'wb')
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=logf)
    r = mujoco.Renderer(m, height=H, width=W)
    t0 = time.time()
    bounds = []
    prev = None
    for j, k in enumerate(idx):
        lab = str(ph[k])
        if lab != prev:
            bounds.append([j / OUT_FPS, lab])
            prev = lab
        d.qpos[:] = q[k]
        d.time = float(k) / fps_src
        mujoco.mj_forward(m, d)
        r.update_scene(d, camera=CAM)
        proc.stdin.write(r.render().tobytes())
        if j % 200 == 0:
            el = time.time() - t0
            print(f'{name} frame {j}/{len(idx)} elapsed_s={el:.1f} fps={j / max(el, 1e-9):.2f}',
                  flush=True)
    proc.stdin.close()
    rc = proc.wait()
    logf.close()
    assert rc == 0, f'ffmpeg rc={rc}'
    assert vid.is_file() and vid.stat().st_size > 50_000, 'video missing/tiny'

    note = ('replay of recorded poses (mj_forward only, zero integration) | full Dex3 hand '
            'mesh collisions (7 finger geoms; fingertip spheres are markers) | mujoco '
            f'{mujoco.__version__} | success=true gates {len(res["gates"])}/{len(res["gates"])} green')
    vtt = OUT / f'{name}.captions.vtt'
    lines = ['WEBVTT', '']
    for i, (t, lab) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else len(idx) / OUT_FPS
        lines += [f'{fmt(t)} --> {fmt(end)}', f'{lab} | {note}', '']
    vtt.write_text('\n'.join(lines), encoding='utf-8')

    hashed = ['result.json', 'trajectory.npz', 'scene.xml', 'g1_free_grasp.xml', 'runtime.json',
              'real-hand-model.json']
    meta = {
        'task': '20261009-132809-qoder-9b946d7f',
        'kind': 'zero_physics_replay_render',
        'source_episode': str(ep),
        'source_sha256': {f: sha(ep / f) for f in hashed if (ep / f).is_file()},
        'video': str(vid), 'video_sha256': sha(vid), 'video_bytes': vid.stat().st_size,
        'frames': int(len(idx)), 'out_fps': OUT_FPS, 'source_fps': fps_src, 'stride': STRIDE,
        'resolution': f'{W}x{H}', 'camera': CAM, 'phase_boundaries_s': bounds,
        'renderer': {'mujoco': mujoco.__version__, 'MUJOCO_GL': os.environ.get('MUJOCO_GL'),
                     'python': sys.version.split()[0], 'executable': sys.executable,
                     'ffmpeg_sha256': sha(FFMPEG)},
        'source_runtime': {'mujoco': src_mujoco,
                           'gate_definition': rt.get('gate_definition'),
                           'contact_solver': rt.get('contact_solver'),
                           'model_sha': rt.get('model_sha'),
                           'contact_model': res.get('contact_model'),
                           'ardy_consumption': res.get('ardy_consumption')},
        'reported_physics': {'success': res['success'],
                             'gates_green': f'{sum(res["gates"].values())}/{len(res["gates"])}',
                             'hold_min_lift_m': res['hold_min_lift_m'],
                             'hold_slip_m': res.get('hold_slip_m'),
                             'max_lift_m': res.get('max_lift_m'),
                             'simulation_steps': res.get('simulation_steps'),
                             'wall_s': res.get('wall_s')},
        'no_source_modification': True, 'physics_steps_in_this_render': 0,
        'written_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    }
    (OUT / f'{name}.manifest.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    print(f'{name} DONE frames={len(idx)} bytes={vid.stat().st_size} sha={meta["video_sha256"][:16]}',
          flush=True)


if __name__ == '__main__':
    main()
