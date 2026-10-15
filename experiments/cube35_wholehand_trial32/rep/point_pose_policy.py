"""Predict a candidate reference through frozen SONIC; correct only that reference."""
import numpy as np,mujoco,copy
import sonic_v11 as s
from task_plan import rot_error
class PointPolicyReference:
 def __init__(self,c):
  self.point_target=None;self.ref_filter=None;self.predicted_action=None;self.c=c;self.f=mujoco.MjData(c.model);self.calls=0;self.probes=0;self.last=None;self.min_singular=1e9;off=0
  for n in c.enc_names:
   if n=='motion_joint_positions_10frame_step5':self.offset=off
   if n=='motion_joint_velocities_10frame_step5':self.voffset=off
   if n=='motion_anchor_orientation_heading_10frame_step5':self.roffset=off
   off+=s.ENC_WIDTHS[n]
 def predict(self,d,goal):
  c=self.c;enc=c.last_encoder.copy()
  if self.ref_filter is None:
   qf=np.tile(goal,(10,1));vf=np.zeros_like(qf)
  else:
   clone=copy.deepcopy(self.ref_filter);qf,vf=clone.step(goal)
  enc[0,self.offset:self.offset+290].reshape(10,29)[:,s.M2I[22:29]]=qf
  enc[0,self.voffset:self.voffset+290].reshape(10,29)[:,s.M2I[22:29]]=vf
  yaw=s.heading(d.qpos[3:7]);cy,sy=np.cos(yaw),np.sin(yaw);ih=np.array([[cy,sy,0],[-sy,cy,0],[0,0,1.]])
  enc[0,self.roffset:self.roffset+60]=np.tile(ih[:,:2].reshape(-1),10)
  values=dict(gyro=d.qvel[3:6].copy(),q=d.qpos[c.aq][s.I2M]-s.DEFAULT_ANGLES[s.I2M],v=d.qvel[c.av][s.I2M].copy(),action=c.last_action.copy(),gravity=s.rotation(d.qpos[3:7]).T@np.array([0.,0.,-1.]))
  hist={key:np.asarray(list(c.hist[key])[1:]+[values[key]]) for key in c.hist}
  parts=dict(token_state=np.zeros(64),his_base_angular_velocity_10frame_step1=hist['gyro'],his_body_joint_positions_10frame_step1=hist['q'],his_body_joint_velocities_10frame_step1=hist['v'],his_last_actions_10frame_step1=hist['action'],his_gravity_dir_10frame_step1=hist['gravity'])
  tok=c.encoder.run(None,{c.encoder.get_inputs()[0].name:enc})[0].reshape(-1);parts['token_state']=tok
  dec=s.pack(parts,c.dec_names,s.DEC_WIDTHS)
  a=c.decoder.run(None,{c.decoder.get_inputs()[0].name:dec})[0].reshape(-1);self.probes+=1
  self.predicted_action=a.copy();self.predicted_encoder=enc.copy();self.predicted_decoder=dec.copy()
  q=np.clip(s.DEFAULT_ANGLES+a[s.M2I]*s.ACTION_SCALE,c.model.jnt_range[c.jids,0],c.model.jnt_range[c.jids,1])
  q[22:29]+=np.clip(d.qpos[c.aq[22:29]]-c.target[22:29],-.025,.025)
  q=np.clip(q,c.model.jnt_range[c.jids,0],c.model.jnt_range[c.jids,1])
  self.f.qpos[:]=d.qpos;self.f.qpos[c.aq[22:29]]=q[22:29];mujoco.mj_kinematics(c.model,self.f);mujoco.mj_comPos(c.model,self.f)
  w=c.model.body('right_wrist_yaw_link').id;return self.f.xpos[w].copy(),self.f.xmat[w].reshape(3,3).copy()
 def feature(self,d,goal,R):
  p,RR=self.predict(d,goal)
  if self.point_target is None:return np.r_[10*p,.12*rot_error(R,RR)]
  m=self.c.model;pts=self.f.geom_xpos[[m.geom('right_thumb_fingertip').id,m.geom('right_middle_fingertip').id]]
  mid=pts.mean(axis=0);return np.r_[10*mid,5*(pts[0,0]-pts[1,0]),5*(pts[0,2]-pts[1,2])]
 def update(self,d,goal,target,R,lo,hi):
  c=self.c;before=c.target.copy();action=c.last_action.copy();x=np.clip(goal,lo,hi);y=self.feature(d,x,R);J=np.zeros((len(y),7));eps=.025
  desired=np.r_[10*target,np.zeros(3)] if self.point_target is None else np.r_[10*self.point_target,0.,0.]
  for j in range(7):
   xx=x.copy();dq=eps if x[j]+eps<=hi[j] else -eps;xx[j]+=dq;J[:,j]=(self.feature(d,xx,R)-y)/dq
  err=desired-y;sv=np.linalg.svd(J,compute_uv=False);delta=J.T@np.linalg.solve(J@J.T+.01*np.eye(len(y)),err);delta*=min(1.,.06/max(abs(delta).max(),1e-12));candidate=np.clip(x+delta,lo,hi)
  accepted=False
  for fraction in [1.,.5,.25]:
   xx=x+fraction*(candidate-x);ee=desired-self.feature(d,xx,R)
   if ee@ee<err@err:accepted=True;candidate=xx;break
  if not accepted:candidate=x
  assert np.array_equal(c.target,before) and np.array_equal(c.last_action,action)
  self.calls+=1;self.min_singular=min(self.min_singular,float(sv[-1]));self.last={'error':err.tolist(),'singular_values':sv.tolist(),'delta':(candidate-x).tolist(),'accepted':accepted,'point_mode':self.point_target is not None}
  self.predict(d,candidate)
  return candidate
 def audit(self):return {'calls':self.calls,'probes':self.probes,'min_singular':self.min_singular,'last':self.last,'body_target_override':False,'history_mutation':False,'kind':'task-feature inverse: wrist position then real-surface marker midpoint and opposed-axis'}