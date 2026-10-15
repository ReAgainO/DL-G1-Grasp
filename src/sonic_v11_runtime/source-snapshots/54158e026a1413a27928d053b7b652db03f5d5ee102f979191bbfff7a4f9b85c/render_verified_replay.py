"""Render recorded physical poses; zero integration and no new experiment."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import mujoco
import numpy as np

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
    assert result['success']
    base_label='FIXED PELVIS' if result['base_fixture'] else 'FREE BASE / FEET SUPPORTED IN HOLD'
    if not result['base_fixture']:
        assert result['whole_body_balance_validated']
        assert all(result['gates'][k] for k in ['feet_supported_in_hold','no_table_rest_in_hold','no_nonfoot_floor_support_in_hold'])
    assert result['runtime_stamp']['mujoco_version'] == mujoco.__version__
    z = np.load(source / 'trajectory.npz', allow_pickle=False)
    assert len(z['time']) == len(z['qpos']) <= 2250
    times = z['time']
    close_start=next(event['time_s'] for event in result['events'] if event['phase']=='CLOSE')
    indices = np.flatnonzero((times >= close_start-1.) & (times <= result['duration_s']))[::2]
    fps = 12.5
    assert 1 <= len(indices) <= 375
    assert np.allclose(np.diff(times[indices]), 1/fps, atol=1e-8)
    model = mujoco.MjModel.from_xml_path(str(source / 'scene.xml'))
    data = mujoco.MjData(model)
    cube = model.body('red_cube').id
    assert model.neq == int(result['base_fixture'])
    if result['base_fixture']:assert model.eq_obj1id[0] == model.body('pelvis').id
    for key, filename in [('scene', 'scene.xml'), ('robot', 'g1_free_grasp.xml')]:
        assert sha(source / filename) == result['runtime_stamp']['model_sha'][key]
    ffmpeg = Path('/home/group4/group4_dasc7606c/envs/render/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2')
    assert ffmpeg.is_file()
    dest.mkdir()
    video = dest / 'grasp.mp4'
    renderer = mujoco.Renderer(model, height=240, width=320)
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
    captions = ['WEBVTT', '']
    def caption_time(t):
        ms = int(round(t*1000)); seconds, millis = divmod(ms, 1000)
        minutes, seconds = divmod(seconds, 60); hours, minutes = divmod(minutes, 60)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}'
    for phase in dict.fromkeys(z['phase'][indices]):
        local = np.flatnonzero(z['phase'][indices] == phase)
        captions += [f'{caption_time(local[0]/fps)} --> {caption_time((local[-1]+1)/fps)}',
            f'{phase} | recorded MuJoCo {mujoco.__version__} | {base_label} / replay, not live',
            f"Simulator-state location; SONIC body + separate fingers; {result['requested_postcapture_lift_height_m']*100:g}cm task retargeting.", '']
    (dest/'captions.vtt').write_text('\n'.join(captions)+'\n')
    cmd = [str(ffmpeg), '-v', 'error', '-nostdin', '-f', 'rawvideo', '-pix_fmt',
           'rgb24', '-s', '640x240', '-r', str(fps), '-i', '-', '-an', '-c:v',
           'libx264', '-threads', '1', '-preset', 'veryfast', '-crf', '20',
           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=logfile)
    try:
        for video_index, k in enumerate(indices):
            data.qpos[:] = z['qpos'][k]
            data.qvel[:] = z['qvel'][k]
            mujoco.mj_forward(model, data)
            panels = []
            for camera in [full, hand]:
                renderer.update_scene(data, camera=camera)
                renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = False
                panels.append(renderer.render().copy())
            canvas = np.concatenate(panels, axis=1)
            phase = str(z['phase'][k])
            proc.stdin.write(canvas.tobytes())
            if phase in {'CLOSE', 'LIFT', 'HOLD', 'RELEASE', 'SETTLE_RELEASE'}:
                if phase not in snapshots:
                    snapshots[phase] = dict(time_s=float(times[k]), video_frame=video_index)
            frame_records.append(dict(time_s=float(times[k]), phase=phase, cube_xyz_m=data.xpos[cube].tolist(), source_frame=int(k)))
        proc.stdin.close()
        assert proc.wait(timeout=30) == 0, 'ffmpeg failed; inspect owned log'
    finally:
        renderer.close()
        logfile.close()
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
    for phase, snapshot in snapshots.items():
        path = dest / ('frame_' + phase + '.png')
        subprocess.run([str(ffmpeg), '-v', 'error', '-nostdin', '-ss',
            str(snapshot['video_frame']/fps), '-i', str(video), '-frames:v', '1',
            '-threads', '1', str(path)], check=True, timeout=20)
        snapshot.update(path=str(path), sha256=sha(path))
    manifest = dict(
        physical_steps=0, new_physical_episodes=0, playback_fps=fps,
        source_pose_fps=25, pose_decimation_stride=2,
        frames=len(indices), video_seconds=len(indices)/fps,
        source_episode=str(source), source_episode_sha256=sha(source/'result.json'),
        source_trajectory_sha256=sha(source/'trajectory.npz'),
        source_episode_runtime_stamp=result['runtime_stamp'],
        runtime_stamp=dict(mujoco_version=mujoco.__version__, sys_executable=sys.executable,
            python_version=sys.version, dt=float(model.opt.timestep),
            model_sha=result['runtime_stamp']['model_sha'], scene_generator_sha=sha(__file__),
            library_sha={'source_episode':sha(source/'result.json'),
                         'source_trajectory':sha(source/'trajectory.npz'),
                         'ffmpeg':sha(ffmpeg)},
            numpy_version=np.__version__),
        limitations=base_label+'; simulator-state object location; explicit postcapture height retargeting and independent finger PD adaptation. Free-base support/contact gates cover HOLD, not full-task COM/COP stability. Initial wrist/table collisions remain in this episode. No full Track4/vision/real robot claim. Recorded qpos replay; zero integration.',
        base_fixture=result['base_fixture'],initial_robot_table_max_normal_N=result['balance_audit_summary']['robot_table_all_max_normal_N'],
        success=result['success'], gates=result['gates'],
        hold_min_lift_m=result['hold_min_lift_m'], hold_slip_m=result['hold_slip_m'],
        video_sha256=sha(video), captions_sha256=sha(dest/'captions.vtt'),
        warning_captions_are_external='Show captions.vtt and limitations alongside video; MP4 contains no burned-in labels.',
        snapshots=snapshots, rendered_frames=frame_records)
    (dest/'replay.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in {'rendered_frames','source_episode_runtime_stamp','runtime_stamp'}}, indent=2))

if __name__ == '__main__':
    main()
