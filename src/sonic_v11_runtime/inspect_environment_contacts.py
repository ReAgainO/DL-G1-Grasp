"""Zero-step reconstruction of contact geometry, NOT recorded contact forces."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import mujoco
import numpy as np

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('episode')
    args = parser.parse_args()
    assert Path(args.episode).name == args.episode
    root = Path(__file__).resolve().parent
    out = root / 'out' / args.episode
    dest = out / 'environment-contact-geometry.json'
    assert not dest.exists()
    r = json.loads((out/'result.json').read_text())
    assert r['runtime_stamp']['mujoco_version'] == mujoco.__version__
    z = np.load(out/'trajectory.npz', allow_pickle=False)
    m = mujoco.MjModel.from_xml_path(str(out/'scene.xml'))
    d = mujoco.MjData(m)
    table = m.geom('table_top').id
    cube = m.geom('red_cube_geom').id
    robot = {m.body('pelvis').id}
    for i in range(1, m.nbody):
        if int(m.body_parentid[i]) in robot:
            robot.add(i)
    assert len(z['time']) <= 2250
    phases = {}
    for k, (q, v) in enumerate(zip(z['qpos'], z['qvel'])):
        d.qpos[:] = q
        d.qvel[:] = v
        mujoco.mj_forward(m, d)
        phase = str(z['phase'][k])
        pairs = phases.setdefault(phase, {})
        assert d.ncon <= 128
        for contact in d.contact[:d.ncon]:
            a, b = map(int, [contact.geom1, contact.geom2])
            if table not in [a, b]:
                continue
            other = b if a == table else a
            if other == cube or int(m.geom_bodyid[other]) not in robot:
                continue
            key = f"{other}:{m.geom(other).name or '<unnamed>'}"
            entry = pairs.setdefault(key, dict(geom_id=other, geom=m.geom(other).name,
                body=m.body(int(m.geom_bodyid[other])).name, minimum_distance_m=float(contact.dist),
                sample_contacts=0, first_time_s=float(z['time'][k]),
                min_distance_time_s=float(z['time'][k]), example_contact_xyz_m=contact.pos.tolist()))
            entry['sample_contacts'] += 1
            if contact.dist < entry['minimum_distance_m']:
                entry.update(minimum_distance_m=float(contact.dist),
                             min_distance_time_s=float(z['time'][k]), example_contact_xyz_m=contact.pos.tolist())
    stamp = dict(mujoco_version=mujoco.__version__, sys_executable=sys.executable,
                 python_version=sys.version, dt=float(m.opt.timestep),
                 model_sha={'scene':sha(out/'scene.xml'),'robot':sha(out/'g1_free_grasp.xml')},
                 scene_generator_sha=sha(__file__), library_sha={'source_episode':sha(out/'result.json'),
                 'source_trajectory':sha(out/'trajectory.npz')})
    answer = dict(runtime_stamp=stamp, source_episode_runtime_stamp=r['runtime_stamp'],
                  physical_steps=0, sample_hz=25, phases=phases,
                  warning='Contacts regenerated from saved 25Hz poses using mj_forward. Candidate geometry only, NOT original solver contacts/forces or 500Hz maxima.')
    dest.write_text(json.dumps(answer, indent=2)+'\n')
    print(json.dumps(dict(physical_steps=0, phases=phases), indent=2))

if __name__ == '__main__':
    main()
