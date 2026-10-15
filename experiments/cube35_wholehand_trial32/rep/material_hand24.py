"""Independent Dex3 controller on fixed original mesh material patches."""
import numpy as np,mujoco
from mesh_contact_v4 import FingerSurfaces
class MaterialHand22:
 def __init__(self,m,plan):
  self.m=m;self.fk=mujoco.MjData(m);self.surfaces=FingerSurfaces(m);self.surfaces.axis=int(plan['axis']);self.surfaces.axis_sign=-float(plan['thumb_side_sign'])
  self.ids=[m.geom(n).id for n in plan['contact_geoms']];self.points_local=np.array(plan['material_points_geom_local']);self.normals_local=np.array(plan['material_normals_geom_local'])
  self.cube_center=np.mean(np.array(plan['targets']),axis=0);self.closed_local=np.array(plan['material_points'])-self.cube_center;self.normal_targets=np.array(plan['material_normals'])
  j=m.actuator_trnid[36:43,0];self.aq=m.jnt_qposadr[j];self.av=m.jnt_dofadr[j];self.lo=m.jnt_range[j,0]+.002;self.hi=m.jnt_range[j,1]-.002;self.active=np.array([0,1,2,5,6]);self.gap=.006;self.preferred=np.array(plan['hand_q']);self.calls=0;self.last=None
 def material(self,f):
  return np.array([f.geom_xpos[k]+f.geom_xmat[k].reshape(3,3)@p for k,p in zip(self.ids,self.points_local)]),np.array([f.geom_xmat[k].reshape(3,3)@n for k,n in zip(self.ids,self.normals_local)])
 def solve(self,d,cube_pos,cube_R,seed,**kwargs):
  m=self.m;f=self.fk;f.qpos[:]=d.qpos;q=np.clip(np.asarray(seed).copy(),self.lo,self.hi);av=self.av[self.active];local=self.closed_local.copy();sg=-self.surfaces.axis_sign;local[0,self.surfaces.axis]+=sg*self.gap;local[1,self.surfaces.axis]-=sg*self.gap
  target=np.asarray(cube_pos)+local@np.asarray(cube_R).T;desired=self.normal_targets@np.asarray(cube_R).T;best=None
  # Compare the last command with the known geometric branch before local IK.
  seeds=[q.copy(),np.clip(self.preferred.copy(),self.lo,self.hi)]
  costs=[]
  for ss in seeds:
   f.qpos[self.aq]=ss;mujoco.mj_kinematics(m,f);mujoco.mj_comPos(m,f);pp,nn=self.material(f);costs.append(np.sum((target-pp)**2)+.005**2*np.sum((desired-nn)**2))
  q=seeds[int(np.argmin(costs))]
  for _ in range(22):
   f.qpos[self.aq]=q;mujoco.mj_kinematics(m,f);mujoco.mj_comPos(m,f);pp,nn=self.material(f);err=np.r_[(target-pp).ravel(),.005*(desired-nn).ravel()];cost=err@err
   if best is None or cost<best[0]:best=(cost,q.copy(),pp.copy())
   jac=[]
   for point,gid in zip(pp,self.ids):
    jp=np.zeros((3,m.nv));mujoco.mj_jac(m,f,jp,None,point,int(m.geom_bodyid[gid]));jac.append(jp[:,av])
   norms=[]
   for n,gid in zip(nn,self.ids):
    jr=np.zeros((3,m.nv));mujoco.mj_jacBody(m,f,None,jr,int(m.geom_bodyid[gid]));skew=np.array([[0,-n[2],n[1]],[n[2],0,-n[0]],[-n[1],n[0],0]]);norms.append(-.005*skew@jr[:,av])
   J=np.vstack([*jac,*norms]);delta=J.T@np.linalg.solve(J@J.T+2e-6*np.eye(12),err);delta*=min(1.,.08/max(abs(delta).max(),1e-12));q[self.active]=np.clip(q[self.active]+delta,self.lo[self.active],self.hi[self.active])
   if np.linalg.norm(target-pp,axis=1).max()<.0003:break
  self.calls+=1;self.last=dict(gap_m=float(self.gap),max_pad_target_error_m=float(np.linalg.norm(target-best[2],axis=1).max()),target_points_m=target.tolist(),achievable_points_m=best[2].tolist(),command_rad=best[1].tolist(),actual_collision_free_certified=False)
  return best[1]
 def audit(self):return dict(kind='material points and normals on original thumb/middle mesh; hand-only IK',calls=self.calls,last=self.last,body_target_override=False,object_state_writes=False)
