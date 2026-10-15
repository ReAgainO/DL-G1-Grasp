"""Static reference planning on enabled physical collision geometry; no physics stepping."""
import os,json,time
from pathlib import Path
import numpy as np,mujoco
from scipy.optimize import least_squares
import sonic_grasp as g,real_hand

root=Path(__file__).resolve().parent;out=root/'out/static_plan02';out.mkdir()
scene,*_=g.scene_and_cal(root,out,direct_table=True,table_front=.24,cube_x=.28,cube_y=-.118)
m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m)
jids=m.actuator_trnid[:,0];aq=m.jnt_qposadr[jids];av=m.jnt_dofadr[jids]
d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[aq[:29]]=g.neutral_body(m,g.s.DEFAULT_ANGLES,.2)
d.qpos[aq[29:]]=0;mujoco.mj_forward(m,d)
base=d.qpos.copy();cube=m.body('red_cube').id;cg=m.geom('red_cube_geom').id;table=m.geom('table_top').id;cp=d.xpos[cube].copy();half=m.geom_size[cg,0]
markers=[m.geom(n).id for n in real_hand.PADS];patch_bodies=[m.body(n).id for n in real_hand.DISTAL]
groups,phys=real_hand.finger_contacts(m)
wrist=m.body('right_wrist_yaw_link').id
handgeoms=phys+[k for k in range(m.ngeom) if m.geom_bodyid[k]==wrist and m.geom_contype[k]!=0]
allowed={m.geom('physical_'+real_hand.DISTAL[0]).id,m.geom('physical_'+real_hand.DISTAL[2]).id}
idx=np.r_[np.arange(22,29),np.arange(36,43)];lo=m.jnt_range[jids[idx],0]+.006;hi=m.jnt_range[jids[idx],1]-.006
arm0=np.array([-1.39100498,-.85828589,1.21619872,.02339199,.75192704,1.55297165,.66138158])
hand_seeds=[np.array([0,-.6,-.94,.1,.08,1.43,.01]),np.array([0,-.4,-1.,.2,.5,1.,.6]),np.array([.4,-.3,-1.2,.5,.5,.8,.8]),np.array([-.4,-.5,-.6,1.4,.08,1.1,.3])]
start=time.monotonic();records=[]
def pose(x):
 d.qpos[:]=base;d.qpos[aq[idx]]=x;mujoco.mj_forward(m,d)
def metrics(x,axis):
 pose(x)
 points=d.geom_xpos[np.array(markers)[[0,2]]].copy()
 normals=np.array([d.xmat[patch_bodies[0]].reshape(3,3)@np.array([-1.,0,0]),d.xmat[patch_bodies[2]].reshape(3,3)@np.array([0.,-1,0])])
 table_dist=np.array([mujoco.mj_geomDistance(m,d,k,table,.2,None) for k in handgeoms])
 cube_dist=np.array([mujoco.mj_geomDistance(m,d,k,cg,.2,None) for k in handgeoms])
 return points,normals,table_dist,cube_dist
for axis in [1,0]:
 targets=np.tile(cp,(2,1));targets[0,axis]-=half-.0002;targets[1,axis]+=half-.0002;targets[:,2]+=.010
 desired_normal=np.zeros((2,3));desired_normal[0,axis]=1;desired_normal[1,axis]=-1
 for si,h in enumerate(hand_seeds):
  armseed=arm0 if si%2==0 else g.core.GRASP
  x0=np.clip(np.r_[armseed,h],lo,hi)
  def residual(x):
   points,normals,td,cd=metrics(x,axis)
   margins=np.array([-.0003 if k in allowed else .002 for k in handgeoms])
   return np.r_[250*(points-targets).ravel(),1.2*(normals-desired_normal).ravel(),300*np.minimum(td-.002,0),300*np.minimum(cd-margins,0),.005*(x-x0)]
  def initial_residual(x):
   points,normals,td,cd=metrics(x,axis)
   return np.r_[300*(points-targets).ravel(),.4*(normals-desired_normal).ravel(),.001*(x-x0)]
  warm=least_squares(initial_residual,x0,bounds=(lo,hi),max_nfev=100,diff_step=1e-5)
  ans=least_squares(residual,warm.x,bounds=(lo,hi),max_nfev=130,diff_step=1e-5,ftol=1e-7,xtol=1e-7,gtol=1e-7)
  points,normals,td,cd=metrics(ans.x,axis)
  r=dict(axis=axis,seed=si,cost=float(ans.cost),nfev=ans.nfev,arm_q=ans.x[:7].tolist(),hand_q=ans.x[7:].tolist(),points=points.tolist(),targets=targets.tolist(),normal=normals.tolist(),position_error_mm=float(np.linalg.norm(points-targets,axis=1).max()*1000),normal_error_deg=np.rad2deg(np.arccos(np.clip((normals*desired_normal).sum(axis=1),-1,1))).tolist(),table_distance_min_mm=float(td.min()*1000),cube_distances_mm={m.geom(k).name:float(v*1000) for k,v in zip(handgeoms,cd)},wall_s=time.monotonic()-start)
  records.append(r);print(json.dumps(r),flush=True)
  (out/'candidates.json').write_text(json.dumps(records,indent=2))
print('BEST',json.dumps(min(records,key=lambda r:r['cost'])),flush=True)
