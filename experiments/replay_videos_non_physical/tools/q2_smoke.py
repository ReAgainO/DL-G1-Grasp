#!/usr/bin/env python3
"""Pre-flight check for the trial32 replay render (TASKID 20261009-132809-qoder-9b946d7f).

No video is written here. This only proves the pieces q2_video.py depends on are present
and that one osmesa frame actually rasterizes, BEFORE we spend a long render run.
Read-only against the source episode.

Usage: q2_smoke.py <episode_name>
"""
import os
import sys
from pathlib import Path

import numpy as np
import mujoco

SRC = Path('/data/group4/20261008-202654-codex-182c4568/rep/out')
W, H = 960, 720
CAM = 'grasp_camera'
FFMPEG = Path('/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/'
              'imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2')

print('python       ', sys.version.split()[0])
print('executable   ', sys.executable)
print('mujoco       ', mujoco.__version__)
print('MUJOCO_GL    ', os.environ.get('MUJOCO_GL'))
print('ffmpeg_exists', FFMPEG.is_file(), FFMPEG)

name = sys.argv[1]
ep = SRC / name
res = {}
import json
res = json.loads((ep / 'result.json').read_text())
print('success      ', res.get('success'))
print('gates_green  ', f"{sum(res['gates'].values())}/{len(res['gates'])}")
rt = res.get('runtime', {})
print('rt_mujoco    ', rt.get('mujoco'), '| renderer', mujoco.__version__)
print('gate_def     ', str(rt.get('gate_definition'))[:120])
print('contact_model', json.dumps(res.get('contact_model'))[:200])
print('ardy_consump ', json.dumps(res.get('ardy_consumption'))[:200])
print('sim_steps    ', res.get('simulation_steps'), 'hold_min_lift_m', res.get('hold_min_lift_m'),
      'hold_slip_m', res.get('hold_slip_m'))

z = np.load(ep / 'trajectory.npz', allow_pickle=False)
print('npz_keys     ', sorted(z.files))
print('qpos_shape   ', z['qpos'].shape, 'phase_len', len(z['phase']), 'fps', int(z['fps']))
print('phase_labels ', sorted(set(str(p) for p in z['phase'])))

m = mujoco.MjModel.from_xml_path(str(ep / 'scene.xml'))
print('nq           ', m.nq, 'ngeom', m.ngeom, 'nmesh', m.nmesh)
print('cameras      ', [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_CAMERA, i)
                        for i in range(m.ncam)])
print('timestep     ', m.opt.timestep, 'integrator', m.opt.integrator, 'cone', m.opt.cone)
print('solver       ', m.opt.solver, 'impratio', m.opt.impratio, 'tolerance', m.opt.tolerance)

# mesh assets must actually load (absolute meshdir in the source xml)
bad = [n for n in range(m.nmesh) if m.mesh_vertnum[n] == 0]
print('mesh_empty   ', len(bad))

d = mujoco.MjData(m)
d.qpos[:] = z['qpos'][0]
mujoco.mj_forward(m, d)
r = mujoco.Renderer(m, height=H, width=W)
r.update_scene(d, camera=CAM)
img = r.render()
print('frame_dtype  ', img.dtype, 'shape', img.shape,
      'nonzero_pixels', int((img.reshape(-1, img.shape[-1]).sum(axis=1) > 0).sum()))
r.close()
print('SMOKE_OK')
