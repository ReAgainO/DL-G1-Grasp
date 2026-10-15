"""Actual saved pad/reference clearance; geometric projection, no dynamics."""
import argparse,copy,json,platform,sys
from pathlib import Path
import mujoco,numpy as np
from finger_clearance import face_target
import source_physics_core as core
from wave4_records import sha
p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.episode,a.output])
folder=root/'out'/a.episode;r=json.loads((folder/'result.json').read_text());stamp=copy.deepcopy(r['runtime_stamp'])
assert stamp['mujoco_version']==mujoco.__version__ and sha(folder/'scene.xml')==stamp['model_sha']['scene']
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'));d=mujoco.MjData(m);f=mujoco.MjData(m)
with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
 assert 2<=len(z['time'])<=2250
 qs=z['qpos'].copy();refs=z['hand_reference'].copy();times=z['time'].copy();phases=z['phase'].copy()
hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];pads=[m.geom(n).id for n in [core.PADS[0],core.PADS[2]]]
cube=m.body('red_cube').id;table=m.geom('table_top').id
ix=np.where(phases=='CLOSE')[0];assert len(ix)>0
d.qpos[:]=qs[ix[0]];f.qpos[:]=d.qpos;recipe=core.CLOSED.copy();recipe[2]=-.88;f.qpos[hq]=recipe;mujoco.mj_forward(m,f)
normal=f.geom_xpos[pads[1]]-f.geom_xpos[pads[0]];normal[2]=0;normal/=np.linalg.norm(normal)
indices=[]
for phase,bound in [('CLOSE',32),('LIFT',64)]:
 selected=np.where(phases==phase)[0];assert len(selected)>0
 indices.extend(selected[np.unique(np.linspace(0,len(selected)-1,min(bound,len(selected))).astype(int))].tolist())
assert len(indices)<=96
rows=[]
for i in indices:
 d.qpos[:]=qs[i];mujoco.mj_forward(m,d);top=float(d.geom_xpos[table,2]+m.geom_size[table,2]);R=d.xmat[cube].reshape(3,3)
 axis=int(np.argmax(abs(R.T@normal)));sign=float(np.sign((R.T@normal)[axis]))
 actual=np.array([d.geom_xpos[g].copy() for g in pads]);radius=np.array([m.geom_size[g,0] for g in pads])
 original=[];constrained=[]
 for point,gid,side in zip(actual,pads,[-1,1]):
  face=side*sign*(.0175+m.geom_size[gid,0]-.0015)
  original.append(face_target(point,d.xpos[cube],R,axis,face,.015))
  constrained.append(face_target(point,d.xpos[cube],R,axis,face,.015,top+m.geom_size[gid,0]+.001))
 f.qpos[:]=d.qpos;f.qpos[hq]=refs[i];mujoco.mj_forward(m,f)
 commanded=np.array([f.geom_xpos[g].copy() for g in pads])
 rows.append(dict(time_s=float(times[i]),phase=str(phases[i]),actual_pad_table_clearance_mm=((actual[:,2]-radius-top)*1000).tolist(),
  commanded_fk_pad_table_clearance_mm=((commanded[:,2]-radius-top)*1000).tolist(),
  unconstrained_target_table_clearance_mm=((np.array(original)[:,2]-radius-top)*1000).tolist(),
  added_floor_target_displacement_mm=(np.linalg.norm(np.array(constrained)-original,axis=1)*1000).tolist(),
  hand_tracking_max_rad=float(np.max(abs(refs[i]-d.qpos[hq])))))
stamp.update(sys_executable=sys.executable,python_version=platform.python_version(),diagnostic_sha256=sha(__file__))
stamp['library_sha']['finger_clearance']=sha(root/'finger_clearance.py')
answer=dict(runtime_stamp=stamp,physical_steps=0,source_episode=a.episode,result_sha256=sha(folder/'result.json'),trajectory_sha256=sha(folder/'trajectory.npz'),
 saved_samples=len(rows),sample_bound=96,approximate_fixed_normal_from_first_saved_CLOSE_frame=normal.tolist(),samples=rows,
 min_actual_clearance_mm=min(min(x['actual_pad_table_clearance_mm']) for x in rows),
 min_commanded_fk_clearance_mm=min(min(x['commanded_fk_pad_table_clearance_mm']) for x in rows),
 max_added_floor_displacement_mm=max(max(x['added_floor_target_displacement_mm']) for x in rows),
 floor_changes_saved_projection_samples=sum(max(x['added_floor_target_displacement_mm'])>1e-6 for x in rows),
 max_hand_tracking_rad=max(x['hand_tracking_max_rad'] for x in rows),
 limitation='Saved25Hz actual state/reference FK and direct projection, not a replay of actual10Hz IK calls or solver warm starts. Fixed closure normal approximated from first saved CLOSE frame; no physical steps or causal proof.')
dest=root/'out'/a.output;assert dest.suffix=='.json'
with dest.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k not in ['runtime_stamp','samples']},indent=2))
