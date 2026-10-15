"""Zero-step table-placement counterfactual on recorded poses, NOT new dynamics."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import mujoco
import numpy as np
import sonic_v11 as s
from sonic_grasp import scene_and_cal

root = Path(__file__).resolve().parent
out = root/'out/table-front-preflight'
out.mkdir()
episode = root/'out/w4_lift15_free327'
r = json.loads((episode/'result.json').read_text())
assert r['runtime_stamp']['mujoco_version'] == mujoco.__version__
z = np.load(episode/'trajectory.npz',allow_pickle=False)
assert len(z['time']) <= 2250
records = []
for front in [.23,.24,.245,.249]:
    dest = out/f'front-{front:.3f}'
    dest.mkdir()
    scene,*_ = scene_and_cal(root,dest,False,True)
    tree = ET.parse(scene)
    table = tree.find(".//geom[@name='table_top']")
    table.set('pos',f'{(.87+front)/2:.12g} 0 0.732')
    table.set('size',f'{(.87-front)/2:.12g} .45 .025')
    tree.write(scene,encoding='utf-8')
    m = mujoco.MjModel.from_xml_path(str(scene))
    d = mujoco.MjData(m)
    tid = m.geom('table_top').id
    cg = m.geom('red_cube_geom').id
    cube_x = float(m.qpos0[m.jnt_qposadr[m.body('red_cube').jntadr]])
    footprint_margin = cube_x-.0175-front
    assert footprint_margin >= .0005-1e-10
    assert m.neq==0 and m.nq==57 and m.nu==43
    assert m.geom_contype[cg] and m.geom_conaffinity[cg]
    robot = {m.body('pelvis').id}
    for i in range(1,m.nbody):
        if int(m.body_parentid[i]) in robot:
            robot.add(i)
    contacts = {}
    for k in np.flatnonzero(z['time'] <= 2.):
        d.qpos[:]=z['qpos'][k]
        d.qvel[:]=z['qvel'][k]
        mujoco.mj_forward(m,d)
        assert d.ncon <=128
        for c in d.contact[:d.ncon]:
            a,b=map(int,[c.geom1,c.geom2])
            if tid not in [a,b]:
                continue
            other=b if a==tid else a
            if int(m.geom_bodyid[other]) not in robot:
                continue
            key=m.body(int(m.geom_bodyid[other])).name
            entry=contacts.setdefault(key,dict(samples=0,min_distance_m=float(c.dist)))
            entry['samples']+=1
            entry['min_distance_m']=min(entry['min_distance_m'],float(c.dist))
    assert not d.qfrc_applied.any() and not d.xfrc_applied.any()
    stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,
        python_version=sys.version,dt=float(m.opt.timestep),
        model_sha={'scene':s.sha(scene),'robot':s.sha(dest/'g1_free_grasp.xml')},
        scene_generator_sha=s.sha(__file__),library_sha={'sonic_grasp':s.sha(root/'sonic_grasp.py'),
        'source_episode':s.sha(episode/'result.json'),'source_trajectory':s.sha(episode/'trajectory.npz')})
    records.append(dict(table_front_x_m=front,table_back_x_m=.87,
        cube_initial_x_m=cube_x,full_cube_footprint_front_margin_m=footprint_margin,
        neutral_recorded_pose_table_contact_geometry=contacts,runtime_stamp=stamp))
answer=dict(physical_steps=0,records=records,
    source_episode_runtime_stamp=r['runtime_stamp'],
    limitations='Same recorded first2s poses, candidate contact geometry only; no force or dynamics recomputed as evidence. New physical trials still required. Table collision and complete cube support retained.')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(dict(physical_steps=0,records=[{k:v for k,v in row.items() if k!='runtime_stamp'} for row in records]),indent=2))
