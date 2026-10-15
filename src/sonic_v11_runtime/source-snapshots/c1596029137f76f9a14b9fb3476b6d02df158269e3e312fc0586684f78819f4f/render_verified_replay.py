"""Render recorded physical poses; zero integration and no new experiment."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('episode')
    parser.add_argument('output_name')
    args = parser.parse_args()
    assert all(Path(x).name == x and x not in {'.', '..'} for x in [args.episode, args.output_name])
    root = Path(__file__).resolve().parent
    source = root / 'out' / args.episode
    dest = root / 'out' / args.output_name
    result = json.loads((source / 'result.json').read_text())
    assert result['success'] and result['base_fixture']
    assert result['runtime_stamp']['mujoco_version'] == mujoco.__version__
    z = np.load(source / 'trajectory.npz', allow_pickle=False)
    assert len(z['time']) == len(z['qpos']) <= 2250
    times = z['time']
    indices = np.flatnonzero((times >= 30.) & (times <= 47.28))
    assert 1 <= len(indices) <= 450
    assert np.allclose(np.diff(times[indices]), .04, atol=1e-8)
    model = mujoco.MjModel.from_xml_path(str(source / 'scene.xml'))
    data = mujoco.MjData(model)
    cube = model.body('red_cube').id
    assert model.neq == 1 and model.eq_obj1id[0] == model.body('pelvis').id
    for key, filename in [('scene', 'scene.xml'), ('robot', 'g1_free_grasp.xml')]:
        assert sha(source / filename) == result['runtime_stamp']['model_sha'][key]
    ffmpeg = Path('/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2')
    font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    assert ffmpeg.is_file() and font_path.is_file()
    font = ImageFont.truetype(str(font_path), 19)
    dest.mkdir()
    video = dest / 'grasp.mp4'
    renderer = mujoco.Renderer(model, height=480, width=640)
    full = mujoco.MjvCamera()
    full.lookat[:] = [.1, 0., .8]
    full.distance = 2.45
    full.azimuth = -115
    full.elevation = -12
    hand = mujoco.MjvCamera()
    hand.lookat[:] = [.275, -.118, .83]
    hand.distance = .60
    hand.azimuth = -125
    hand.elevation = -15
    snapshots = {}
    frame_records = []
    logfile = (dest / 'ffmpeg.log').open('wb')
    cmd = [str(ffmpeg), '-v', 'error', '-nostdin', '-f', 'rawvideo', '-pix_fmt',
           'rgb24', '-s', '1280x524', '-r', '25', '-i', '-', '-an', '-c:v',
           'libx264', '-threads', '1', '-preset', 'veryfast', '-crf', '20',
           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=logfile)
    try:
        for k in indices:
            data.qpos[:] = z['qpos'][k]
            data.qvel[:] = z['qvel'][k]
            mujoco.mj_forward(model, data)
            panels = []
            for camera in [full, hand]:
                renderer.update_scene(data, camera=camera)
                panels.append(renderer.render().copy())
            canvas = Image.new('RGB', (1280, 524), 'black')
            canvas.paste(Image.fromarray(np.concatenate(panels, axis=1)), (0, 44))
            draw = ImageDraw.Draw(canvas)
            phase = str(z['phase'][k])
            draw.text((10, 1), f"Recorded MuJoCo {mujoco.__version__} | t={times[k]:.2f}s | {phase}", fill='white', font=font)
            draw.text((10, 23), 'FIXED PELVIS / simulator-state location / SONIC body + independent fingers / replay, not live', fill='#ffcc66', font=font)
            proc.stdin.write(canvas.tobytes())
            if phase in {'CLOSE', 'LIFT', 'HOLD', 'RELEASE', 'SETTLE_RELEASE'}:
                snapshot = dest / ('frame_' + phase + '.png')
                if not snapshot.exists():
                    canvas.save(snapshot)
                    snapshots[phase] = dict(time_s=float(times[k]), path=str(snapshot), sha256=sha(snapshot))
            frame_records.append(dict(time_s=float(times[k]), phase=phase, cube_xyz_m=data.xpos[cube].tolist(), source_frame=int(k)))
        proc.stdin.close()
        assert proc.wait(timeout=30) == 0, 'ffmpeg failed; inspect owned log'
    finally:
        renderer.close()
        logfile.close()
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
    manifest = dict(
        physical_steps=0, new_physical_episodes=0, playback_fps=25,
        frames=len(indices), video_seconds=len(indices)/25,
        source_episode=str(source), source_episode_sha256=sha(source/'result.json'),
        source_trajectory_sha256=sha(source/'trajectory.npz'),
        source_episode_runtime_stamp=result['runtime_stamp'],
        runtime_stamp=dict(mujoco_version=mujoco.__version__, sys_executable=sys.executable,
            python_version=sys.version, dt=float(model.opt.timestep),
            model_sha=result['runtime_stamp']['model_sha'], scene_generator_sha=sha(__file__),
            library_sha={'source_episode':sha(source/'result.json'),
                         'source_trajectory':sha(source/'trajectory.npz'),
                         'ffmpeg':sha(ffmpeg), 'font':sha(font_path)},
            numpy_version=np.__version__, pillow_version=pillow_version),
        limitations='Fixed pelvis; model-based object location; postcapture 15cm task retargeting. No full Track4/vision/real robot claim. Rendered from recorded qpos; no physics integration.',
        success=result['success'], gates=result['gates'],
        hold_min_lift_m=result['hold_min_lift_m'], hold_slip_m=result['hold_slip_m'],
        video_sha256=sha(video), snapshots=snapshots, rendered_frames=frame_records)
    (dest/'replay.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in {'rendered_frames','source_episode_runtime_stamp','runtime_stamp'}}, indent=2))

if __name__ == '__main__':
    main()
