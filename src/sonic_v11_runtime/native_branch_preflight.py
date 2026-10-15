"""Test selected-source branch search on existing saved approach states."""
import argparse
import json
from pathlib import Path
import mujoco
import numpy as np
import sonic_v11 as s
import source_physics_core as core
from motion_input import ArdyMotion
from sonic_grasp import ik,pinch_center
from native_branch import select_native_branch

p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');p.add_argument('--at-clearance',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(x).name==x for x in [a.episode,a.output])
folder=root/'out'/a.episode;output=root/'out'/a.output;assert not output.exists()
r=json.loads((folder/'result.json').read_text());assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'))
for key,file in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:assert s.sha(folder/file)==r['runtime_stamp']['model_sha'][key]
with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
    assert len(z['qpos'])<=2250
    indices=np.flatnonzero(z['phase']=='APPROACH')
    if a.at_clearance:
        start=next(e['time_s'] for e in r['events'] if e['phase']=='APPROACH')
        qualified=start+r['clearance_approach']['clearance_passed_time_s']
        index=int(next(i for i in indices if z['time'][i]>=qualified))
    else:index=int(indices[-1])
    d=mujoco.MjData(m);d.qpos[:]=z['qpos'][index];d.qvel[:]=z['qvel'][index];time=float(z['time'][index])
mujoco.mj_forward(m,d)
motion=ArdyMotion(Path(r['source']['source_npz']))
assert motion.audit['source_npz_sha256']==r['source']['source_npz_sha256']
qa=m.jnt_qposadr[m.actuator_trnid[:29,0]];va=m.jnt_dofadr[m.actuator_trnid[:29,0]]
hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]]
cube=m.body('red_cube').id;wrist=m.body('right_wrist_yaw_link').id
hand=core.CLOSED.copy();hand[2]=-.88
q,audit=select_native_branch(m,d,qa[22:29],va[22:29],hq,hand,
    d.xpos[cube].copy()+[0,0,.1],d.xmat[cube].reshape(3,3).copy(),
    motion.qpos[:,29:36],motion.qpos[r['native_orientation_frame'],29:36],2,ik,pinch_center)
output.mkdir();answer=dict(physical_steps=0,source_episode=a.episode,saved_time_s=time,
    actual_wrist_z_m=float(d.xpos[wrist,2]),sample_at_clearance=a.at_clearance,source=motion.audit,
    source_result_sha256=s.sha(folder/'result.json'),branch=audit,module_sha256=s.sha(root/'native_branch.py'),
    physical_grasp_established=False)
(output/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
