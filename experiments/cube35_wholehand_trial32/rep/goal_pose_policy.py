"""Predict a candidate reference through frozen SONIC; correct only that reference."""
import numpy as np,mujoco
import sonic_v11 as s
from task_plan import rot_error
class GoalPoseReference:
 def __init__(self,c):
  self.c=c;self.f=mujoco.MjData(c.model);self.calls=0;self.probes=0;self.last=None;self.min_singular=1e9;off=0
  for n in c.enc_names:
   if n=='motion_joint_positions_10frame_step5':self.offset=off
   if n=='motion_joint_velocities_10frame_step5':self.voffset=off
   off+=s.ENC_WIDTHS[n]
 def predict(self,d,goal):
  c=self.c;enc=c.last_encoder.copy();pos=enc[0,self.offset:self.offset+290].reshape(10,29);pos[:,s.M2I[22:29]]=goal
  enc[0,self.voffset:self.voffset+290].reshape(10,29)[:,s.M2I[22:29]]=0
  tok=c.encoder.run(None,{c.encoder.get_inputs()[0].name:enc})[0].reshape(-1);dec=c.last_decoder.copy();dec[0,:64]=tok
  a=c.decoder.run(None,{c.decoder.get_inputs()[0].name:dec})[0].reshape(-1);self.probes+=1
  q=np.clip(s.DEFAULT_ANGLES+a[s.M2I]*s.ACTION_SCALE,c.model.jnt_range[c.jids,0],c.model.jnt_range[c.jids,1])
  q[22:29]+=np.clip(d.qpos[c.aq[22:29]]-c.target[22:29],-.025,.025)
  q=np.clip(q,c.model.jnt_range[c.jids,0],c.model.jnt_range[c.jids,1])
  self.f.qpos[:]=d.qpos;self.f.qpos[c.aq[22:29]]=q[22:29];mujoco.mj_kinematics(c.model,self.f);mujoco.mj_comPos(c.model,self.f)
  w=c.model.body('right_wrist_yaw_link').id;return self.f.xpos[w].copy(),self.f.xmat[w].reshape(3,3).copy()
 def update(self,d,goal,target,R,lo,hi):
  c=self.c;before=c.target.copy();action=c.last_action.copy();x=np.clip(goal,lo,hi);p0,R0=self.predict(d,x);J=np.zeros((6,7));eps=.025
  for j in range(7):
   xx=x.copy();dq=eps if x[j]+eps<=hi[j] else -eps;xx[j]+=dq;pp,RR=self.predict(d,xx);J[:,j]=np.r_[10*(pp-p0),rot_error(RR,R0)]/dq
  err=np.r_[10*(target-p0),rot_error(R,R0)];sv=np.linalg.svd(J,compute_uv=False)
  delta=J.T@np.linalg.solve(J@J.T+.005*np.eye(6),err);delta*=min(1.,.3/max(abs(delta).max(),1e-12));candidate=np.clip(x+delta,lo,hi)
  # Backtrack on the actual frozen model, rather than trusting a large local linear step.
  accepted=False
  for fraction in [1.,.5,.25]:
   xx=x+fraction*(candidate-x);pp,RR=self.predict(d,xx);ee=np.r_[10*(target-pp),rot_error(R,RR)]
   if ee@ee<err@err:accepted=True;candidate=xx;break
  if not accepted:candidate=x
  assert np.array_equal(c.target,before) and np.array_equal(c.last_action,action)
  self.calls+=1;self.min_singular=min(self.min_singular,float(sv[-1]));self.last={'error':err.tolist(),'singular_values':sv.tolist(),'delta':(candidate-x).tolist(),'accepted':accepted}
  return candidate
 def audit(self):return {'calls':self.calls,'probes':self.probes,'min_singular':self.min_singular,'last':self.last,'body_target_override':False,'history_mutation':False,'kind':'candidate-goal frozen SONIC pose inverse with backtracking'}