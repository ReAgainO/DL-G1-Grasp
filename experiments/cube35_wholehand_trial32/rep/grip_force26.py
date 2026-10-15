"""Normal-force closure regulator after capture, acting only on seven hand targets."""
import numpy as np,mujoco
class GripForce26:
 def __init__(self,m,hand_qpos,hand_dofs,anchors,capture_hand,axis,thumb_side_sign):
  self.m=m;self.f=mujoco.MjData(m);self.aq=np.asarray(hand_qpos);self.av=np.asarray(hand_dofs);self.anchors=anchors;self.q0=np.array(capture_hand).copy();self.axis=int(axis);self.sign=float(thumb_side_sign)
  self.filtered=np.array([a['normal_N'] for a in anchors]);self.compression=np.full(2,.0002);self.target_N=1.2;self.calls=0;self.max_compression=np.zeros(2);self.last=None
 def update(self,d,group_forces,dt=.002):
  self.filtered+=dt/(.03+dt)*(np.asarray(group_forces)[[0,2]]-self.filtered)
  self.compression=np.clip(self.compression+dt*.0002*(self.target_N-self.filtered),0.,.0025);self.max_compression=np.maximum(self.max_compression,self.compression)
  f=self.f;f.qpos[:]=d.qpos;mujoco.mj_kinematics(self.m,f);mujoco.mj_comPos(self.m,f);cube_R=f.xmat[self.m.body('red_cube').id].reshape(3,3);J=[]
  for a,side in zip(self.anchors,[-self.sign,self.sign]):
   gg=a['geom'];p=f.geom_xpos[gg]+f.geom_xmat[gg].reshape(3,3)@np.array(a['local_point']);jp=np.zeros((3,self.m.nv));mujoco.mj_jac(self.m,f,jp,None,p,int(self.m.geom_bodyid[gg]));n=f.geom_xmat[gg].reshape(3,3)@np.array(a['local_normal']);n/=max(np.linalg.norm(n),1e-12);J.append(n@jp[:,self.av])
  J=np.array(J);delta=J.T@np.linalg.solve(J@J.T+1e-5*np.eye(2),self.compression);delta=np.clip(delta,-.06,.06);q=self.q0+delta;self.calls+=1
  self.last=dict(filtered_normal_N=self.filtered.tolist(),closure_compression_m=self.compression.tolist(),delta_joint_rad=delta.tolist());return q
 def audit(self):return dict(kind='fixed captured finger shape + independent normal closure-force regulation via real collision contact anchors; position targets only',target_normal_force_per_digit_N=self.target_N,compression_cap_m=.0025,joint_offset_cap_rad=.06,captured_command_rad=self.q0.tolist(),normal_frame="captured collision normal transported with the physical finger link; does not chase cube world position",max_compression_m=self.max_compression.tolist(),calls=self.calls,last=self.last,body_target_override=False,object_state_writes=False,external_force_injection=False)
