"""Read original solver contacts and test INITIAL pose clearance; no mj_step.

Candidates change simulation initialization only. They are not a collision-free
motion planner or a balance certificate, and must be tested through SONIC.
"""
import argparse
import csv
import gzip
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
from sonic_v11 import sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('episode')
    parser.add_argument('output')
    args = parser.parse_args()
    assert all(Path(x).name == x for x in [args.episode, args.output])
    root = Path(__file__).resolve().parent
    episode = root / 'out' / args.episode
    output = root / 'out' / args.output
    assert not output.exists()
    result = json.loads((episode / 'result.json').read_text())
    assert result['runtime_stamp']['mujoco_version'] == mujoco.__version__
    model = mujoco.MjModel.from_xml_path(str(episode / 'scene.xml'))
    assert sha(episode / 'scene.xml') == result['runtime_stamp']['model_sha']['scene']
    assert sha(episode / 'g1_free_grasp.xml') == result['runtime_stamp']['model_sha']['robot']
    source = episode / 'robot_support_contacts.csv.gz'
    phases = {}
    rows = 0
    with gzip.open(source, 'rt') as stream:
        prefix = stream.readline()
        assert prefix.startswith('# runtime_stamp=')
        assert json.loads(prefix.split('=', 1)[1]) == result['runtime_stamp']
        for row in csv.DictReader(stream):
            rows += 1
            assert rows <= 1440000
            if row['support_geom_name'] != 'table_top':
                continue
            key = row['phase'] + '/' + row['robot_body']
            entry = phases.setdefault(key, dict(contacts=0, first_time_s=float(row['solver_time_s']),
                last_time_s=0., maximum_single_contact_normal_N=0., minimum_contact_distance_m=1.))
            entry['contacts'] += 1
            entry['last_time_s'] = float(row['solver_time_s'])
            entry['maximum_single_contact_normal_N'] = max(entry['maximum_single_contact_normal_N'], float(row['normal_force_N']))
            entry['minimum_contact_distance_m'] = min(entry['minimum_contact_distance_m'], float(row['distance_m']))
    with np.load(episode / 'trajectory.npz', allow_pickle=False) as z:
        assert len(z['qpos']) <= 2250 and z['qpos'].shape[1] == model.nq
        first_pose = z['qpos'][0].copy()
    # Reconstruct explicit initialization, not the already-integrated first frame.
    from sonic_v11 import DEFAULT_ANGLES
    from source_physics_core import OPEN
    initial = mujoco.MjData(model)
    initial.qpos[:3] = [0., 0., .788740]
    initial.qpos[3:7] = [1., 0., 0., 0.]
    body_jids = model.actuator_trnid[:29, 0]
    initial.qpos[model.jnt_qposadr[body_jids]] = DEFAULT_ANGLES
    right_hand = model.actuator_trnid[36:43, 0]
    initial.qpos[model.jnt_qposadr[right_hand]] = OPEN
    mujoco.mj_forward(model, initial)
    table = model.geom('table_top').id
    robot_bodies = {model.body('pelvis').id}
    for body in range(1, model.nbody):
        if int(model.body_parentid[body]) in robot_bodies:
            robot_bodies.add(body)
    geoms = [g for g in range(model.ngeom) if int(model.geom_bodyid[g]) in robot_bodies
        and ((int(model.geom_contype[g]) & int(model.geom_conaffinity[table]))
             or (int(model.geom_contype[table]) & int(model.geom_conaffinity[g])))]
    assert 1 <= len(geoms) <= 128
    def clearance(data):
        distances = [(float(mujoco.mj_geomDistance(model, data, g, table, .2, None)), g) for g in geoms]
        distance, geom = min(distances)
        contacts = [float(c.dist) for c in data.contact[:data.ncon]
                    if table in [int(c.geom1), int(c.geom2)]
                    and int(model.geom_bodyid[c.geom2 if c.geom1 == table else c.geom1]) in robot_bodies]
        return dict(minimum_robot_table_distance_m=distance,
            closest_body=model.body(int(model.geom_bodyid[geom])).name,
            table_contact_count=len(contacts), minimum_contact_distance_m=min(contacts, default=None))
    original = clearance(initial)
    ids = [model.joint(side + joint).id for side in ['left_', 'right_']
           for joint in ['shoulder_pitch_joint', 'elbow_joint']]
    addresses = model.jnt_qposadr[ids]
    candidates = []
    for pitch in [0., .1, .2, .3, .4, -.1, -.2]:
        for elbow in [0., .2, .4, .6, -.2, -.4]:
            candidate = mujoco.MjData(model)
            candidate.qpos[:] = initial.qpos
            delta = np.array([pitch, elbow, pitch, elbow])
            candidate.qpos[addresses] += delta
            within = bool(np.all(candidate.qpos[addresses] >= model.jnt_range[ids, 0] + .002)
                          and np.all(candidate.qpos[addresses] <= model.jnt_range[ids, 1] - .002))
            if not within:
                continue
            mujoco.mj_forward(model, candidate)
            stats = clearance(candidate)
            stats.update(pitch_delta_rad=pitch, elbow_delta_rad=elbow,
                         adjustment_norm_rad=float(np.linalg.norm(delta)),
                         body_q= candidate.qpos[model.jnt_qposadr[body_jids]].tolist(),
                         feasible_initial_table_clearance=stats['minimum_robot_table_distance_m'] >= .005)
            candidates.append(stats)
    feasible = sorted((x for x in candidates if x['feasible_initial_table_clearance']),
                      key=lambda x: (x['adjustment_norm_rad'], -x['minimum_robot_table_distance_m']))
    stamp = dict(mujoco_version=mujoco.__version__, sys_executable=sys.executable,
                 python_version=sys.version, model_sha=result['runtime_stamp']['model_sha'],
                 scene_generator_sha=sha(__file__), dt=float(model.opt.timestep),
                 library_sha={'episode':sha(episode/'result.json'), 'trajectory':sha(episode/'trajectory.npz'),
                    'solver_contacts':sha(source), 'sonic_v11':sha(root/'sonic_v11.py'),
                    'source_physics_core':sha(root/'source_physics_core.py'),
                    'official_action_adapter':sha(root/'official_refs/sonic_action_adapter.py')})
    answer = dict(runtime_stamp=stamp, source_episode_runtime_stamp=result['runtime_stamp'],
        physical_steps=0, original_solver_contact_rows=rows, phase_body_contacts=phases,
        initialization=original, candidate_limit=42, candidates=candidates,
        feasible_count=len(feasible), best=feasible[0] if feasible else None,
        saved_first_frame_is_not_initialization=True,
        first_saved_base_xyz_m=first_pose[:3].tolist(),
        limits='Initial table clearance only; no physical integration, collision-free path, COM/COP or equilibrium certificate. Initial pose adaptation is labelled separately from algorithm performance.')
    output.mkdir()
    (output/'result.json').write_text(json.dumps(answer, indent=2)+'\n')
    print(json.dumps({k:v for k,v in answer.items() if k not in ['runtime_stamp','source_episode_runtime_stamp','candidates']}, indent=2))


if __name__ == '__main__':
    main()
