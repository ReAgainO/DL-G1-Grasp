import json,time
from pathlib import Path
import numpy as np,mujoco
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
import real_hand,sonic_grasp as g
root=Path.cwd();out=root/'out/pose_plan04';out.mkdir()
scene,*_=g.scene_and_cal(root,out,direct_table=True,table_front=.24,cube_x=.28,cube_y=-.118)
m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m);jids=m.actuator_trnid[:,0];qa=m.jnt_qposadr[jids]
d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[qa[:29]]=g.neutral_body(m,g.s.DEFAULT_ANGLES,.2)
hand=np.asarray(min(json.load(open(root/'out/hand_only_candidates.json')),key=lambda x:x['cost'])['hand_q']);d.qpos[qa[36:43]]=hand;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
w=m.body('right_wrist_yaw_link').id;R0=d.xmat[w].reshape(3,3).copy();p0=d.xpos[w].copy();markers=[m.geom(n).id for n in real_hand.PADS]
ps=(d.geom_xpos[np.array(markers)[[0,2]]]-p0)@R0
center=ps.mean(axis=0);n=ps[1]-ps[0];n/=np.linalg.norm(n)
ez=np.array([0.,0,1.]);ez-=n*(n@ez);ez/=np.linalg.norm(ez);ex=np.cross(n,ez);B=np.column_stack([ex,n,ez])
cube=m.body('red_cube').id;cg=m.geom('red_cube_geom').id;table=m.geom('table_top').id;cp=d.xpos[cube].copy();cp[2]+=.008
physical=real_hand.finger_contacts(m)[1]
handgeoms=physical+[k for k in range(m.ngeom) if m.geom_bodyid[k]==w and m.geom_contype[k]!=0]
base=d.qpos.copy();lo=m.jnt_range[jids[22:29],0]+.005;hi=m.jnt_range[jids[22:29],1]-.005
armseed=np.array([-1.391,-.858,1.216,.023,.752,1.553,.661]);records=[]
for axis in [1,0]:
 W=np.diag([-1.,-1.,1.]) if axis==1 else np.array([[0,-1,0],[1,0,0],[0,0,1.]])
 for angle in [45,60,75,90]:
  ax=np.array([0.,1,0]) if axis==1 else np.array([1.,0,0])
  R=Rotation.from_rotvec(np.deg2rad(angle)*ax).as_matrix()@W@B.T;target=cp-R@center
  for si,seed in enumerate([armseed,g.core.GRASP,g.s.DEFAULT_ANGLES[22:29]]):
   def f(q):
    d.qpos[:]=base;d.qpos[qa[22:29]]=q;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
    return np.r_[250*(d.xpos[w]-target),2*g.rot_error(R,d.xmat[w].reshape(3,3))]
   o=least_squares(f,np.clip(seed,lo,hi),bounds=(lo,hi),max_nfev=80)
   f(o.x);error=np.linalg.norm(d.xpos[w]-target);rot=np.linalg.norm(g.rot_error(R,d.xmat[w].reshape(3,3)))
   if error>.005 or rot>.1:continue
   mujoco.mj_collision(m,d)
   td=np.full(len(handgeoms),.02);cd=np.full(len(handgeoms),.02)
   for contact in d.contact[:d.ncon]:
    for target_geom,distances in [(table,td),(cg,cd)]:
     if target_geom in (contact.geom1,contact.geom2):
      other=contact.geom2 if contact.geom1==target_geom else contact.geom1
      if other in handgeoms:distances[handgeoms.index(other)]=min(distances[handgeoms.index(other)],contact.dist)
   # Direct vertex-plane clearance supplements actual collision contacts.
   for ii,gg in enumerate(handgeoms):
    if m.geom_type[gg]==mujoco.mjtGeom.mjGEOM_MESH:
     mm=m.geom_dataid[gg];vv=m.mesh_vert[m.mesh_vertadr[mm]:m.mesh_vertadr[mm]+m.mesh_vertnum[mm]]
     ww=vv@d.geom_xmat[gg].reshape(3,3).T+d.geom_xpos[gg]
     inxy=(ww[:,0]>.24)&(ww[:,0]<.87)&(abs(ww[:,1])<.45)
     if inxy.any():td[ii]=min(td[ii],float(ww[inxy,2].min()-.757))
   allowed={m.geom('physical_'+real_hand.DISTAL[0]).id,m.geom('physical_'+real_hand.DISTAL[2]).id}
   margins=np.array([-.001 if k in allowed else .001 for k in handgeoms])
   score=max(0,.002-td.min())*1000+np.maximum(margins-cd,0).sum()*1000+error*1000
   r={'axis':axis,'roll_deg':angle,'seed':si,'score':float(score),'arm_q':o.x.tolist(),'hand_q':hand.tolist(),'wrist_target':target.tolist(),'wrist_R':R.tolist(),'grasp_center':cp.tolist(),'position_error_mm':float(error*1000),'angle_error_deg':float(np.rad2deg(rot)),'table_min_mm':float(td.min()*1000),'cube_dist_mm':{m.geom(k).name or 'wrist'+str(k):float(x*1000) for k,x in zip(handgeoms,cd)},'marker_points':d.geom_xpos[markers].tolist()}
   records.append(r)
(root/'out/pose_plan_candidates.json').write_text(json.dumps(records,indent=2))
print('SOLVED',len(records))
for r in sorted(records,key=lambda x:x['score'])[:6]:print(json.dumps(r))