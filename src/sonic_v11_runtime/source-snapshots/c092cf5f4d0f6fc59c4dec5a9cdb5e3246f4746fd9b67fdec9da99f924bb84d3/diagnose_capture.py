"""Saved-state capture diagnosis; no integration or live state writes."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import mujoco
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('episode')
    args = parser.parse_args()
    assert Path(args.episode).name == args.episode
    root = Path(__file__).resolve().parent
    folder = root/'out'/args.episode
    dest = folder/'capture-diagnosis.json'
    assert not dest.exists()
    result = json.loads((folder/'result.json').read_text())
    assert result['runtime_stamp']['mujoco_version'] == mujoco.__version__
    z = np.load(folder/'trajectory.npz', allow_pickle=False)
    rows = np.loadtxt(folder/'telemetry.csv.gz', delimiter=',', comments='#')
    assert len(z['time']) <= 2250 and len(rows) <= 45000
    model = mujoco.MjModel.from_xml_path(str(folder/'scene.xml'))
    data = mujoco.MjData(model)
    wrist = model.body('right_wrist_yaw_link').id
    cube = model.body('red_cube').id
    names = ['right_thumb_fingertip', result['opposing_pad']]
    pads = [model.geom(name).id for name in names]
    hj = model.actuator_trnid[36:43, 0]
    hq = model.jnt_qposadr[hj]
    lift_event = next((event for event in result['events'] if event['phase'] == 'LIFT'), None)
    if lift_event is None:
        print(json.dumps(dict(episode=args.episode, lift_not_reached=True)))
        return
    lift_start = lift_event['time_s']
    sample_times = [lift_start-.24, lift_start-.08, lift_start]
    sample_times += list(lift_start+np.arange(.2, 2.41, .2))
    sample_times += [lift_start+4, lift_start+6, lift_start+7.9]
    chosen = sorted(set(int(np.argmin(abs(z['time']-time))) for time in sample_times))
    records = []
    origin = origin_R = None
    for k in chosen:
        data.qpos[:] = z['qpos'][k]
        data.qvel[:] = z['qvel'][k]
        mujoco.mj_forward(model, data)
        pos = data.xpos[cube].copy()
        rot = data.xmat[cube].reshape(3, 3).copy()
        wp = data.xpos[wrist].copy()
        wr = data.xmat[wrist].reshape(3, 3).copy()
        if origin is None and z['time'][k] >= lift_start:
            origin, origin_R = wp.copy(), wr.copy()
        points = np.asarray([data.geom_xpos[pad].copy() for pad in pads])
        local = (points-pos)@rot
        hand_error = z['hand_reference'][k]-data.qpos[hq]
        ti = int(np.argmin(abs(rows[:, 0]-z['time'][k])))
        tele = rows[ti]
        target = z['wrist_target'][k]
        records.append(dict(time_s=float(z['time'][k]), phase=str(z['phase'][k]),
            since_lift_s=float(z['time'][k]-lift_start), cube_position_m=pos.tolist(),
            recorded_cube_force_N=tele[7:11].tolist(), cube_in_wrist_m=tele[4:7].tolist(),
            pad_center_cube_local_m=local.tolist(), pad_distance_m=float(np.linalg.norm(points[1]-points[0])),
            pad_radii_m=[float(model.geom_size[pad, 0]) for pad in pads],
            actual_hand_rad=data.qpos[hq].tolist(), command_hand_rad=z['hand_reference'][k].tolist(),
            command_minus_actual_hand_rad=hand_error.tolist(),
            wrist_position_m=wp.tolist(), wrist_target_m=target.tolist() if np.isfinite(target).all() else None,
            wrist_target_error_m=float(np.linalg.norm(target-wp)) if np.isfinite(target).all() else None,
            wrist_displacement_m=(wp-origin).tolist() if origin is not None else None,
            wrist_orientation_change_rad=float(np.arccos(np.clip((np.trace(origin_R.T@wr)-1)/2, -1, 1))) if origin_R is not None else None,
            base_position_m=data.qpos[:3].tolist()))
    stamp = dict(mujoco_version=mujoco.__version__, sys_executable=sys.executable,
        python_version=sys.version, dt=float(model.opt.timestep),
        model_sha={'scene':sha(folder/'scene.xml'), 'robot':sha(folder/'g1_free_grasp.xml')},
        scene_generator_sha=sha(__file__), library_sha={'source_result':sha(folder/'result.json'),
        'source_trajectory':sha(folder/'trajectory.npz'), 'source_telemetry':sha(folder/'telemetry.csv.gz')})
    answer = dict(runtime_stamp=stamp, physical_steps=0, source_episode=args.episode,
        source_episode_runtime_stamp=result['runtime_stamp'], records=records,
        limitations='25Hz pose FK reconstruction; forces are nearest original 500Hz telemetry. No claim of contact-force reconstruction, continuous-time extrema, or exact capture pose.')
    dest.write_text(json.dumps(answer, indent=2)+'\n')
    compact = [dict(since_lift_s=round(row['since_lift_s'], 3), force_N=row['recorded_cube_force_N'],
        pad_local_mm=(1000*np.asarray(row['pad_center_cube_local_m'])).round(3).tolist(),
        hand_error_max_rad=float(np.max(abs(np.asarray(row['command_minus_actual_hand_rad'])))),
        wrist_error_mm=None if row['wrist_target_error_m'] is None else round(1000*row['wrist_target_error_m'], 3)) for row in records]
    print(json.dumps(dict(episode=args.episode, physical_steps=0, records=compact), indent=2))


if __name__ == '__main__':
    main()
