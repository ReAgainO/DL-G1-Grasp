"""Saved-state grasp-direction tracking audit; no physics or force inference."""
import argparse,copy,json
from pathlib import Path
import mujoco,numpy as np
from motion_input import ArdyMotion
import source_physics_core as core
from wave4_records import sha
p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');a=p.parse_args();root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.episode,a.output])
folder=root/'out'/a.episode;r=json.loads((folder/'result.json').read_text())
assert r['branch_face_alignment_enabled'] and r['runtime_stamp']['mujoco_version']==mujoco.__version__
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'));d=mujoco.MjData(m);f=mujoco.MjData(m)
source=Path(r['motion_profile']['roles']['reach']['source_npz']);motion=ArdyMotion(source,check_csv=source.with_suffix('.csv'))
bq=m.jnt_qposadr[np.array([m.joint(n).id for n in motion.joint_names])];aq=bq[22:29];hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]]
pads=[m.geom(n).id for n in [core.PADS[0],core.PADS[2]]];cube=m.body('red_cube').id;wrist=m.body('right_wrist_yaw_link').id
recipe=core.CLOSED.copy();recipe[2]=-.88;branch=r['post_clearance_native_branch'];assert branch['selected']['static_feasible']
f.qpos[:]=branch['search_state']['qpos'];f.qpos[aq]=branch['selected']['body_q'];f.qpos[hq]=recipe;mujoco.mj_forward(m,f)
normal=f.geom_xpos[pads[1]]-f.geom_xpos[pads[0]];normal[2]=0;normal/=np.linalg.norm(normal)
axis=int(np.argmax(abs(f.xmat[cube].reshape(3,3).T@normal)))
with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
 assert 2<=len(z['time'])<=2250;qs=z['qpos'].copy();refs=z['body_reference'].copy();ts=z['time'].copy();phases=z['phase'].copy()
samples=[]
for phase in ['APPROACH','PREGRASP','DESCEND','ALIGN','CLOSE']:
 idx=np.where(phases==phase)[0]
 if not len(idx):continue
 for i in idx[np.unique(np.linspace(0,len(idx)-1,min(32,len(idx))).astype(int))]:
  d.qpos[:]=qs[i];mujoco.mj_forward(m,d);R=d.xmat[cube].reshape(3,3).copy();goal=R[:,axis].copy();goal[2]=0.;goal/=np.linalg.norm(goal)
  angles=[]
  for body in [d.qpos[bq],refs[i]]:
   f.qpos[:]=d.qpos;f.qpos[bq]=body;f.qpos[hq]=recipe;mujoco.mj_forward(m,f)
   v=f.geom_xpos[pads[1]]-f.geom_xpos[pads[0]];v[2]=0.
   angle=None if np.linalg.norm(v)<.005 else float(np.degrees(np.arccos(np.clip(abs((v/np.linalg.norm(v))@goal),-1,1))))
   angles.append(angle)
  samples.append(dict(time_s=float(ts[i]),phase=phase,actual_closed_recipe_yaw_error_deg=angles[0],virtual_reference_closed_recipe_yaw_error_deg=angles[1],cube_z_m=float(d.xpos[cube,2]),wrist_z_m=float(d.xpos[wrist,2])))
assert len(samples)<=160
answer=dict(runtime_stamp=r['runtime_stamp'],physical_steps=0,script_sha256=sha(__file__),result_sha256=sha(folder/'result.json'),trajectory_sha256=sha(folder/'trajectory.npz'),
 selected_cube_axis=axis,samples=samples,sample_bound=160,by_phase={})
for phase in sorted(set(x['phase'] for x in samples)):
 rows=[x for x in samples if x['phase']==phase]
 actual=[x['actual_closed_recipe_yaw_error_deg'] for x in rows if x['actual_closed_recipe_yaw_error_deg'] is not None]
 reference=[x['virtual_reference_closed_recipe_yaw_error_deg'] for x in rows if x['virtual_reference_closed_recipe_yaw_error_deg'] is not None]
 answer['by_phase'][phase]=dict(first=rows[0],last=rows[-1],max_actual_yaw_deg=max(actual,default=None),max_reference_yaw_deg=max(reference,default=None),invalid_actual_samples=len(rows)-len(actual),invalid_reference_samples=len(rows)-len(reference))
answer['limitation']='25Hz saved-state FK with virtual CLOSED recipe; not measured finger contacts, not a causal proof or actual10Hz hand controller replay. Invalid/degenerate directions remain null.'
dest=root/'out'/a.output;assert dest.suffix=='.json'
with dest.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k not in ['samples','runtime_stamp']},indent=2))
