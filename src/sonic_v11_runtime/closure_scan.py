"""Offline closure geometry/force audit of saved physical data, zero stepping."""
import json,sys
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s,source_physics_core as core
root=Path(__file__).resolve().parent;folder=root/'out'/sys.argv[1];out=folder/'closure-scan.json';assert not out.exists()
r=json.loads((folder/'result.json').read_text());z=np.load(folder/'trajectory.npz',allow_pickle=False)
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'));d=mujoco.MjData(m);cube=m.body('red_cube').id;pads=[m.geom(n).id for n in core.PADS];hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]]
rows=np.loadtxt(folder/r.get('telemetry_schema',{}).get('path','telemetry.csv'),comments='#',delimiter=',')
start=next(e['time_s'] for e in r['events'] if e['phase']=='CLOSE');ix=np.flatnonzero(z['phase']=='CLOSE');assert 0<len(ix)<=300
records=[]
for i in ix:
 d.qpos[:]=z['qpos'][i];d.qvel[:]=z['qvel'][i];mujoco.mj_forward(m,d);center=d.xpos[cube];R=d.xmat[cube].reshape(3,3);positions=d.geom_xpos[pads].copy();gaps=[];normal=[]
 for pos,pad in zip(positions,pads):
  local=R.T@(pos-center);dist=abs(local)-.0175;gaps.append(float(np.linalg.norm(np.maximum(dist,0))+min(np.max(dist),0)-m.geom_size[pad,0]))
  closest=np.clip(local,-.0175,.0175);v=local-closest;normal.append((R@(v/max(np.linalg.norm(v),1e-12))).tolist())
 ti=int(np.argmin(abs(rows[:,0]-z['time'][i])))
 records.append(dict(time_s=float(z['time'][i]),since_close_s=float(z['time'][i]-start),cube=center.tolist(),pads=positions.tolist(),hand_rad=d.qpos[hq].tolist(),
                     sphere_to_cube_surface_gap_m=gaps,estimated_outward_surface_normals=normal,forces_N=rows[ti,7:10].tolist(),support_N=float(rows[ti,10])))
selected=[min(records,key=lambda x:abs(x['since_close_s']-t)) for t in [0,.5,1,2,4.9]]
x=rows[rows[:,0]>=start];both=(x[:,7:10]>.1).sum(axis=1)>=2;best=run=0
for value in both:run=run+1 if value else 0;best=max(best,run)
result=dict(source_runtime_stamp=r['runtime_stamp'],analysis_runtime_stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,model_sha={'scene':s.sha(folder/'scene.xml'),'robot':s.sha(folder/'g1_free_grasp.xml')},scene_generator_sha=s.sha(__file__),library_sha={'trajectory':s.sha(folder/'trajectory.npz')},dt=.002),physical_steps=0,
 min_pad_surface_gaps_m=np.min([x['sphere_to_cube_surface_gap_m'] for x in records],axis=0).tolist(),longest_two_fingers_above_point1N_s=best*.002,selected_records=selected)
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if 'stamp' not in k},indent=2))
