"""Separate named-finger IK. Body state/targets and object state are never written.

Plan thumb plus one opposing pad on opposite horizontal cube support faces.
This is a task controller using simulator object coordinates, NOT ARDY output.
"""
import numpy as np,mujoco
import source_physics_core as core
from finger_clearance import face_target

class AdaptiveHand:
 def __init__(self,m,opponent=2,preload_m=.0005,face_half_m=.015,cube_half_m=None):
  if not np.isfinite(preload_m) or not .00025<=preload_m<=.0025:raise ValueError('finger pad geometric preload must be finite and 0.25..2.5mm')
  if not np.isfinite(face_half_m) or not .006<=face_half_m<=.015:raise ValueError('finger tangential face half-region must be finite and 6..15mm')
  # A3/H1' MAIN CAUSE: the pad face coordinate used to be
  #   side*axis_sign*(.0175 + m.geom_size[gid,0] - preload_m)
  # i.e. it already read the live PAD radius m.geom_size[gid,0] but then added a
  # hardcoded .0175 for the CUBE half-width (= the 35mm template cube). On any
  # other cube edge the pad target lands off the real face (20mm cube: 7.5mm
  # outside each face => the fingers never touch it). Read the cube half-extent
  # live from the model; cube_half_m stays as an explicit override for tests.
  # At the default 35mm scene the live value is the same double as .0175, so the
  # baseline trajectory is bit-identical.
  self.cube_half_m=float(m.geom_size[m.geom('red_cube_geom').id,0]) if cube_half_m is None else float(cube_half_m)
  if not np.isfinite(self.cube_half_m) or not .004<=self.cube_half_m<=.030:raise ValueError('cube half-extent must be finite and 4..30mm')
  self.m=m;self.opponent=opponent;self.preload_m=float(preload_m);self.face_half_m=float(face_half_m);self.fk=mujoco.MjData(m)
  joints=m.actuator_trnid[36:43,0];self.aq=m.jnt_qposadr[joints];self.av=m.jnt_dofadr[joints]
  self.lo=m.jnt_range[joints,0]+.002;self.hi=m.jnt_range[joints,1]-.002
  self.active=np.r_[np.arange(3),np.arange(3,5) if opponent==1 else np.arange(5,7)]
  self.ids=[m.geom(core.PADS[i]).id for i in [0,opponent]];self.calls=0;self.last=None
 def solve(self,d,cube_pos,cube_R,seed,normal=None,table_top_z=None,table_clearance_m=0.):
  if table_top_z is not None and (not np.isfinite(table_top_z) or not .5<=table_top_z<=1. or not np.isfinite(table_clearance_m) or not 0.<=table_clearance_m<=.005):raise ValueError('Bounded table/finger clearance required')
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
    minimum_z=None if table_top_z is None else table_top_z+table_clearance_m
    targets.append(face_target(point,cube_pos,R,axis,side*axis_sign*(self.cube_half_m-self.preload_m),self.face_half_m,minimum_z))
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
   target_points_m=best[3].tolist(),achievable_points_m=best[2].tolist(),command_rad=best[1].tolist(),normal=n.tolist(),opposing_cube_axis=axis,table_top_z_m=table_top_z,table_clearance_m=table_clearance_m,table_target_constraint_active=table_top_z is not None,actual_collision_free_certified=False)
  return best[1]
 def audit(self):return dict(calls=self.calls,body_target_override=False,object_state_writes=False,object_localization='simulator state, not vision',geometric_pad_preload_m=self.preload_m,tangential_face_half_region_m=self.face_half_m,face_region_definition='target centres remain inside the selected cube face region; actual contact margin still requires physics validation',preload_definition='finger IK target penetration only; not a physical object weld/force injection or a measured-force guarantee',last=self.last)
