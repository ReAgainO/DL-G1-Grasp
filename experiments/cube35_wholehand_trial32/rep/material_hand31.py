"""Independent Dex3 controller on fixed original mesh material patches."""
import numpy as np,mujoco
from mesh_contact_v4 import FingerSurfaces
class MaterialHand22:
 def __init__(self,m,plan):
  self.m=m;self.fk=mujoco.MjData(m);self.surfaces=FingerSurfaces(m);self.surfaces.axis=int(plan['axis']);self.surfaces.axis_sign=-float(plan['thumb_side_sign'])
  self.ids=[m.geom(n).id for n in plan['contact_geoms']];self.points_local=np.array(plan['material_points_geom_local']);self.normals_local=np.array(plan['material_normals_geom_local'])
  self.cube_center=np.mean(np.array(plan['targets']),axis=0);self.closed_local=np.array(plan['material_points'])-self.cube_center;self.closed_local[:,2]+=.004;self.normal_targets=np.array(plan['material_normals'])
  j=m.actuator_trnid[36:43,0];self.aq=m.jnt_qposadr[j];self.av=m.jnt_dofadr[j];self.lo=m.jnt_range[j,0]+.002;self.hi=m.jnt_range[j,1]-.002;self.active=np.array([0,1,2,5,6]);self.table_geoms=[];self.table_vertices=[];self.table_top=None;self.table_front=None;self.gap=.012;self.preferred=np.array(plan['hand_q']);self.calls=0;self.last=None
 def set_table(self,d,clearance=.003):
  from real_hand import finger_contacts
  _,geoms=finger_contacts(self.m);table=self.m.geom('table_top').id
  self.table_top=float(d.geom_xpos[table,2]+self.m.geom_size[table,2]);self.table_front=float(d.geom_xpos[table,0]-self.m.geom_size[table,0]);self.clearance=clearance
  for gg in geoms:
   if self.m.geom_type[gg]==mujoco.mjtGeom.mjGEOM_MESH:
    mm=self.m.geom_dataid[gg];vv=self.m.mesh_vert[self.m.mesh_vertadr[mm]:self.m.mesh_vertadr[mm]+self.m.mesh_vertnum[mm]].astype(float)
   else:vv=np.array([[x,y,z] for x in [-1,1] for y in [-1,1] for z in [-1,1]])*self.m.geom_size[gg]
   self.table_geoms.append(gg);self.table_vertices.append(vv)
 def table_terms(self,f,av):
  residual=[];jac=[]
  for gg,vv in zip(self.table_geoms,self.table_vertices):
   world=vv@f.geom_xmat[gg].reshape(3,3).T+f.geom_xpos[gg];selection=np.flatnonzero(world[:,0]>=self.table_front-.002)
   row=np.zeros(len(av));err=0.
   if len(selection):
    point=world[selection[np.argmin(world[selection,2])]];err=max(0.,self.table_top+self.clearance-point[2])
    if err:
     jp=np.zeros((3,self.m.nv));mujoco.mj_jac(self.m,f,jp,None,point,int(self.m.geom_bodyid[gg]));row=jp[2,av]
   residual.append(4*err);jac.append(4*row)
  return np.array(residual),np.array(jac)
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
   f.qpos[self.aq]=q;mujoco.mj_kinematics(m,f);mujoco.mj_comPos(m,f);pp,nn=self.material(f)
   # A side pinch permits tangential motion inside a measured safe face region.
   # Keep material patch fixed on each physical mesh; only the face target
   # slides. Height stays within3mm of cube/hover centre to avoid top-edge load.
   loc=(pp-np.asarray(cube_pos))@np.asarray(cube_R);tang=1-self.surfaces.axis
   free=local.copy();free[:,tang]=np.clip(loc[:,tang],-.009,.009);free[:,2]=np.clip(loc[:,2],.003,.005);target=np.asarray(cube_pos)+free@np.asarray(cube_R).T
   table_error,table_jac=self.table_terms(f,av);err=np.r_[(target-pp).ravel(),.005*(desired-nn).ravel(),table_error];cost=err@err
   if best is None or cost<best[0]:best=(cost,q.copy(),pp.copy(),target.copy())
   jac=[]
   for point,gid in zip(pp,self.ids):
    jp=np.zeros((3,m.nv));mujoco.mj_jac(m,f,jp,None,point,int(m.geom_bodyid[gid]));jac.append(jp[:,av])
   norms=[]
   for n,gid in zip(nn,self.ids):
    jr=np.zeros((3,m.nv));mujoco.mj_jacBody(m,f,None,jr,int(m.geom_bodyid[gid]));skew=np.array([[0,-n[2],n[1]],[n[2],0,-n[0]],[-n[1],n[0],0]]);norms.append(-.005*skew@jr[:,av])
   J=np.vstack([*jac,*norms,table_jac]);delta=J.T@np.linalg.solve(J@J.T+2e-6*np.eye(len(err)),err);delta*=min(1.,.08/max(abs(delta).max(),1e-12));q[self.active]=np.clip(q[self.active]+delta,self.lo[self.active],self.hi[self.active])
   if np.linalg.norm(target-pp,axis=1).max()<.0003 and max(table_error,default=0.)<.00005:break
  self.calls+=1;self.last=dict(gap_m=float(self.gap),max_pad_target_error_m=float(np.linalg.norm(best[3]-best[2],axis=1).max()),target_points_m=best[3].tolist(),achievable_points_m=best[2].tolist(),command_rad=best[1].tolist(),target_table_clearance_m=self.clearance,actual_collision_free_certified=False)
  return best[1]
 def audit(self):return dict(kind='material points and normals on original thumb/middle mesh; hand-only IK',calls=self.calls,last=self.last,body_target_override=False,object_state_writes=False)
