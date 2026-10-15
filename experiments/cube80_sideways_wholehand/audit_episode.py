"""Independent replay evidence; no re-integration or changes to prior results."""
import json,sys
from pathlib import Path
import numpy as np,mujoco
R=Path(__file__).resolve().parent;out=R/'out'/sys.argv[1]
r=json.loads((out/'result.json').read_text());z=np.load(out/'trajectory.npz',allow_pickle=False)
m=mujoco.MjModel.from_xml_path(str(out/'scene.xml'));d=mujoco.MjData(m)
w=m.body('right_wrist_yaw_link').id;cb=m.body('red_cube').id;cube=m.geom('red_cube_geom').id;table=m.geom('table_top').id
local=[];world=[];rootR=[];thumb=[];opp=[];tableforce=[];bfeet=[];nonfoot=[];depths=[];poseR=[]
for q,v in zip(z['qpos'],z['qvel']):
 d.qpos[:]=q;d.qvel[:]=v;mujoco.mj_forward(m,d);A=d.xmat[w].reshape(3,3)
 local.append(A.T@(d.xpos[cb]-d.xpos[w]));world.append(d.xpos[cb]-d.xpos[w]);poseR.append(A.copy())
 tf=of=tb=fn=other=0.;deep=0.
 for i,c in enumerate(d.contact):
  f=np.zeros(6);mujoco.mj_contactForce(m,d,i,f);F=max(0.,float(f[0]))
  if cube in [c.geom1,c.geom2]:
   g=c.geom2 if c.geom1==cube else c.geom1;name=m.body(int(m.geom_bodyid[g])).name;deep=min(deep,float(c.dist))
   if 'right_hand_thumb' in name:tf+=F
   if 'right_hand_index' in name or 'right_hand_middle' in name:of+=F
   if int(g)==table:tb+=F
  if m.geom('floor').id in [c.geom1,c.geom2]:
   g=c.geom2 if c.geom1==m.geom('floor').id else c.geom1;name=m.body(int(m.geom_bodyid[g])).name
   if name.startswith(('left_ankle','right_ankle')):fn+=F
   elif name not in ['world']:other+=F
 thumb.append(tf);opp.append(of);tableforce.append(tb);bfeet.append(fn);nonfoot.append(other);depths.append(deep)
local=np.array(local);world=np.array(world);times=z['time'];hold=z['phase']=='HOLD';lift=np.flatnonzero(z['phase']=='TEST_LIFT')[0]
holdi=np.flatnonzero(hold);relative={'world_vector_slip_alllift_m':float(np.linalg.norm(world[lift:]-world[lift],axis=1).max()),
 'wristlocal_slip_alllift_m':float(np.linalg.norm(local[lift:]-local[lift],axis=1).max()),
 'world_vector_slip_hold_m':float(np.linalg.norm(world[holdi]-world[holdi[0]],axis=1).max()) if len(holdi) else None,
 'wristlocal_slip_hold_m':float(np.linalg.norm(local[holdi]-local[holdi[0]],axis=1).max()) if len(holdi) else None}
geoms=[]
for g in range(m.ngeom):
 n=m.body(int(m.geom_bodyid[g])).name
 if n.startswith(('left_hand_','right_hand_')) and m.geom_contype[g]:geoms.append({'body':n,'geom':m.geom(g).name,'type':int(m.geom_type[g]),'mask':[int(m.geom_contype[g]),int(m.geom_conaffinity[g])]})
report={'episode':str(out),'runtime_version':mujoco.__version__,'replay_only':True,'physics_steps':0,'raw_success':r['success'],'relative_metrics':relative,
 'min_hold_cube_height_increase_m':float((z['cube_pos'][hold,2]-z['cube_pos'][0,2]).min()) if hold.any() else None,
 'hold_frames':int(hold.sum()),'hold_floor_nonfoot_peak_N':float(np.array(nonfoot)[hold].max()) if hold.any() else None,
 'hold_feet_min_N':float(np.array(bfeet)[hold].min()) if hold.any() else None,
 'note_contact_forces':'Replay mj_forward original XML lacks in-memory margin/inertia changes; force numbers are diagnostic only, not trusted runtime replacement.',
 'max_cube_contact_depth_original_xml_m':min(depths),'wholehand_geoms':geoms}
(out/'independent_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
