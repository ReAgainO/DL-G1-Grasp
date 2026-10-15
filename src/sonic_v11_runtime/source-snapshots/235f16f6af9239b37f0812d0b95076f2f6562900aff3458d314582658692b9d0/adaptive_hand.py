"""Separate named-finger IK. Body state/targets and object state are never written.

Plan thumb plus one opposing pad on opposite horizontal cube support faces.
This is a task controller using simulator object coordinates, NOT ARDY output.
"""
import numpy as np,mujoco
import source_physics_core as core

class AdaptiveHand:
 def __init__(self,m,opponent=2):
  self.m=m;self.opponent=opponent;self.fk=mujoco.MjData(m)
  joints=m.actuator_trnid[36:43,0];self.aq=m.jnt_qposadr[joints];self.av=m.jnt_dofadr[joints]
  self.lo=m.jnt_range[joints,0]+.002;self.hi=m.jnt_range[joints,1]-.002
  self.active=np.r_[np.arange(3),np.arange(3,5) if opponent==1 else np.arange(5,7)]
  self.ids=[m.geom(core.PADS[i]).id for i in [0,opponent]];self.calls=0;self.last=None
 def solve(self,d,cube_pos,cube_R,seed,normal=None):
  m=self.m;f=self.fk;f.qpos[:]=d.qpos;q=np.clip(np.asarray(seed),self.lo,self.hi);f.qpos[self.aq]=q;mujoco.mj_forward(m,f)
  points=np.array([f.geom_xpos[i].copy() for i in self.ids])
  if normal is None:normal=points[1]-points[0]
  n=np.asarray(normal).copy();n[2]=0.
  if np.linalg.norm(n)<.005:n=np.array([1.,0,0])
  n/=np.linalg.norm(n);R=np.asarray(cube_R);axis=int(np.argmax(abs(R.T@n)));axis_sign=float(np.sign((R.T@n)[axis]))
  av=self.av[self.active];jp=np.zeros((3,m.nv));best=None
  for _ in range(35):
   f.qpos[self.aq]=q;mujoco.mj_forward(m,f)
   pos=np.array([f.geom_xpos[i].copy() for i in self.ids]);targets=[]
   # Fingers need opposed contact anywhere on two faces, not at their centres.
   # Tangential coordinates inside the physical face are free (no false exact
   # centre constraint); outside coordinates are projected onto a 2.5mm margin.
   for point,gid,side in zip(pos,self.ids,[-1,1]):
    local=R.T@(point-cube_pos);target=np.clip(local,-.015,.015)
    target[axis]=side*axis_sign*(.0175+m.geom_size[gid,0]-.0005)
    targets.append(cube_pos+R@target)
   targets=np.array(targets);error=(targets-pos).reshape(-1)
   cost=float(error@error)
   if best is None or cost<best[0]:best=(cost,q.copy(),pos.copy(),targets.copy())
   J=[]
   for gid in self.ids:
    mujoco.mj_jacGeom(m,f,jp,None,gid);J.append(jp[:,av].copy())
   J=np.vstack(J);delta=J.T@np.linalg.solve(J@J.T+1e-5*np.eye(6),error)
   delta*=min(1.,.10/max(abs(delta).max(),1e-12));q[self.active]=np.clip(q[self.active]+delta,self.lo[self.active],self.hi[self.active])
   if np.max(np.linalg.norm(targets-pos,axis=1))<.0005:break
  self.calls+=1;self.last=dict(max_pad_target_error_m=float(np.max(np.linalg.norm(best[3]-best[2],axis=1))),
   target_points_m=best[3].tolist(),achievable_points_m=best[2].tolist(),command_rad=best[1].tolist(),normal=n.tolist(),opposing_cube_axis=axis)
  return best[1]
 def audit(self):return dict(calls=self.calls,body_target_override=False,object_state_writes=False,object_localization='simulator state, not vision',last=self.last)
