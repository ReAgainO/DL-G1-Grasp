"""Frozen-observation NN reference Jacobian. Never modifies policy state or body targets."""
import numpy as np,mujoco
import sonic_v11 as s
from task_plan import rot_error
class PosePolicyReference:
 def __init__(self,c):
  self.c=c;self.f=mujoco.MjData(c.model);self.calls=0;self.probes=0;self.min_singular=1e9;self.last=None
  off=0;self.offset=None
  for name in c.enc_names:
   if name=='motion_joint_positions_10frame_step5':self.offset=off
   off+=s.ENC_WIDTHS[name]
  assert self.offset is not None
 def pose(self,d,action):
  c=self.c;m=c.model;self.f.qpos[:]=d.qpos
  q=np.clip(s.DEFAULT_ANGLES+action[s.M2I]*s.ACTION_SCALE,m.jnt_range[c.jids,0],m.jnt_range[c.jids,1])
  self.f.qpos[c.aq[22:29]]=q[22:29];mujoco.mj_kinematics(m,self.f);mujoco.mj_comPos(m,self.f)
  w=m.body('right_wrist_yaw_link').id;return self.f.xpos[w].copy(),self.f.xmat[w].reshape(3,3).copy()
 def update(self,d,reference,target,R,lo,hi):
  c=self.c;m=c.model;w=m.body('right_wrist_yaw_link').id
  if c.last_encoder is None or c.last_decoder is None:return reference.copy()
  p0,R0=self.pose(d,c.last_action);J=np.zeros((6,7));eps=.025
  before_target=c.target.copy();before_action=c.last_action.copy()
  for j in range(7):
   enc=c.last_encoder.copy();addr=self.offset+np.arange(10)*29+s.M2I[22+j];dq=eps
   if enc[0,addr].max()+dq>hi[j]:dq=-eps
   if enc[0,addr].min()+dq<lo[j]:continue
   enc[0,addr]+=dq
   tok=c.encoder.run(None,{c.encoder.get_inputs()[0].name:enc})[0].reshape(-1)
   dec=c.last_decoder.copy();dec[0,:64]=tok
   action=c.decoder.run(None,{c.decoder.get_inputs()[0].name:dec})[0].reshape(-1)
   pp,RR=self.pose(d,action);J[:,j]=np.r_[10*(pp-p0),rot_error(RR,R0)]/dq;self.probes+=1
  err=np.r_[10*(np.asarray(target)-d.xpos[w]),rot_error(R,d.xmat[w].reshape(3,3))]
  singular=np.linalg.svd(J,compute_uv=False);self.min_singular=min(self.min_singular,float(singular[-1]))
  delta=J.T@np.linalg.solve(J@J.T+.002*np.eye(6),err);delta*=min(1.,.12/max(abs(delta).max(),1e-12))
  assert np.array_equal(c.target,before_target) and np.array_equal(c.last_action,before_action)
  self.calls+=1;self.last={'error':err.tolist(),'singular_values':singular.tolist(),'delta':delta.tolist()}
  return np.clip(reference+delta,lo,hi)
 def audit(self):return {'calls':self.calls,'probes':self.probes,'min_singular':self.min_singular,'last':self.last,'history_mutation':False,'body_target_override':False}