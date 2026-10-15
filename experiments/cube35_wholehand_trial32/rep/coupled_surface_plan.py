"""Static coupled full-mesh feasibility. No stepping or physical-success claim."""
import json,time
from pathlib import Path
import numpy as np,mujoco
from scipy.optimize import least_squares
from mesh_contact_v4 import FingerSurfaces,closest_triangle_info
r=Path(__file__).resolve().parent;o=r/'out/surface_plan22';o.mkdir()
m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial16/scene.xml'));d=mujoco.MjData(m)
tr=np.load(r/'out/normal_trial16/trajectory.npz');base=tr['qpos'][0].copy();cap=tr['qpos'][np.flatnonzero(tr['phase']=='TEST_LIFT')[0]].copy()
j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];idx=np.r_[np.arange(22,29),np.arange(36,43)]
lo=m.jnt_range[j[idx],0]+.035;hi=m.jnt_range[j[idx],1]-.035
table=m.geom('table_top').id;cube=m.geom('red_cube_geom').id;cb=int(m.geom_bodyid[cube]);w=m.body('right_wrist_yaw_link').id
d.qpos[:]=base;mujoco.mj_forward(m,d);cp=d.geom_xpos[cube].copy();half=float(m.geom_size[cube,0])
sur=FingerSurfaces(m);allowed=set(sur.ids)
# Robot bodies determined by ancestral pelvis, not numerical IDs.
pel=m.body('pelvis').id
def robotbody(b):
 while b:
  if b==pel:return True
  b=int(m.body_parentid[b])
 return False
geoms=[k for k in range(m.ngeom) if robotbody(int(m.geom_bodyid[k])) and m.geom_contype[k]];slots={k:i for i,k in enumerate(geoms)}
patch=[];pnormal=[]
for gid,tris,ns,marker in zip(sur.ids,sur.tris,sur.normals,['right_thumb_fingertip','right_middle_fingertip']):
 p=d.geom_xmat[gid].reshape(3,3).T@(d.geom_xpos[m.geom(marker).id]-d.geom_xpos[gid]);p,i=closest_triangle_info(p,tris);patch.append(p);pnormal.append(ns[i])
patch=np.array(patch);pnormal=np.array(pnormal);tic=time.monotonic();results=[]
def pose(x):
 d.qpos[:]=base;d.qpos[qa[idx]]=x;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
 return np.array([d.geom_xpos[k]+d.geom_xmat[k].reshape(3,3)@p for k,p in zip(sur.ids,patch)]),np.array([d.geom_xmat[k].reshape(3,3)@n for k,n in zip(sur.ids,pnormal)])
def collision():
 mujoco.mj_collision(m,d);pen=np.zeros((3,len(geoms)))
 for c in d.contact[:d.ncon]:
  a,b=int(c.geom1),int(c.geom2)
  if table in [a,b]:
   other=b if a==table else a
   if other in slots:pen[0,slots[other]]=max(pen[0,slots[other]],max(0.,-c.dist+.0003))
  elif a in slots and b in slots:
   depth=max(0.,-c.dist-.00005)
   pen[1,slots[a]]=max(pen[1,slots[a]],depth);pen[1,slots[b]]=max(pen[1,slots[b]],depth)
  elif cube in [a,b]:
   other=b if a==cube else a
   if other in slots and other not in allowed:pen[2,slots[other]]=max(pen[2,slots[other]],max(0.,-c.dist+.0005))
 return pen.ravel()
for axis in [1,0]:
 for sign in [1.,-1.]:
  targets=np.tile(cp,(2,1));targets[0,axis]+=sign*(half-.0006);targets[1,axis]-=sign*(half-.0006)
  desired=np.zeros((2,3));desired[0,axis]=-sign;desired[1,axis]=sign
  for si in range(2):
   seed=cap[qa[idx]].copy()
   if si:seed[4]+=.5;seed[6]-=.4;seed[7:10]=[.2,-.4,-1.];seed[12:]=[1.25,.3]
   seed=np.clip(seed,lo+1e-6,hi-1e-6)
   def fun(x,coll):
    pp,nn=pose(x);reg=.003*(x-seed);reg[10:12]=.025*(x[10:12]-[1.3,1.7])
    rr=np.r_[150*(pp-targets).ravel(),1.5*(nn-desired).ravel(),reg]
    return np.r_[rr,500*collision()] if coll else rr
   warm=least_squares(lambda x:fun(x,False),seed,bounds=(lo,hi),max_nfev=150,ftol=1e-8,xtol=1e-8,gtol=1e-8)
   ans=least_squares(lambda x:fun(x,True),warm.x,bounds=(lo,hi),max_nfev=160,diff_step=1e-5,ftol=1e-7,xtol=1e-7,gtol=1e-7)
   pp,nn=pose(ans.x);pen=collision()
   rec=dict(axis=axis,thumb_side_sign=sign,seed=si,q=ans.x.tolist(),arm_q=ans.x[:7].tolist(),hand_q=ans.x[7:].tolist(),material_points=pp.tolist(),material_normals=nn.tolist(),material_points_geom_local=patch.tolist(),material_normals_geom_local=pnormal.tolist(),contact_geoms=[m.geom(k).name for k in sur.ids],targets=targets.tolist(),max_point_error_mm=float(np.linalg.norm(pp-targets,axis=1).max()*1000),normal_error_deg=np.rad2deg(np.arccos(np.clip(np.sum(nn*desired,axis=1),-1,1))).tolist(),max_penalty_mm=float(pen.max()*1000),wrist_xyz=d.xpos[w].tolist(),wrist_R=d.xmat[w].reshape(3,3).tolist(),joint_margin_rad=float(np.minimum(ans.x-m.jnt_range[j[idx],0],m.jnt_range[j[idx],1]-ans.x).min()),cost=float(ans.cost),wall_s=time.monotonic()-tic,physics_success=False)
   results.append(rec);(o/'candidates.json').write_text(json.dumps(results,indent=2));print(json.dumps(rec),flush=True)
   if time.monotonic()-tic>210:break
  if time.monotonic()-tic>210:break
 if time.monotonic()-tic>210:break
print('BEST',json.dumps(min(results,key=lambda x:x['cost'])),flush=True)
