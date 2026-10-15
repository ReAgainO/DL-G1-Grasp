"""Quasistatic SONIC feedback rollout for input-side task-point adjustment.
No real state/target/history writes; virtual joint follower is an approximation.
"""
import numpy as np,mujoco
import sonic_v11 as s
from task_plan import rot_error
class SteadyPointReference:
 def __init__(self,c):
  self.c=c;self.f=mujoco.MjData(c.model);self.calls=0;self.probes=0;self.last=None;self.min_singular=1e9;self.point_target=None;off=0
  for n in c.enc_names:
   if n=='motion_joint_positions_10frame_step5':self.offset=off
   if n=='motion_joint_velocities_10frame_step5':self.voffset=off
   if n=='motion_anchor_orientation_heading_10frame_step5':self.roffset=off
   off+=s.ENC_WIDTHS[n]
 def predict(self,d,goal):
  c=self.c;m=c.model;enc=c.last_encoder.copy();enc[0,self.offset:self.offset+290].reshape(10,29)[:,s.M2I[22:29]]=goal;enc[0,self.voffset:self.voffset+290].reshape(10,29)[:,s.M2I[22:29]]=0
  yaw=s.heading(d.qpos[3:7]);cy,sy=np.cos(yaw),np.sin(yaw);ih=np.array([[cy,sy,0],[-sy,cy,0],[0,0,1.]])
  enc[0,self.roffset:self.roffset+60]=np.tile(ih[:,:2].reshape(-1),10);tok=c.encoder.run(None,{c.encoder.get_inputs()[0].name:enc})[0].reshape(-1)
  hist={key:[v.copy() for v in c.hist[key]] for key in c.hist};q=d.qpos[c.aq].copy();vel=np.zeros(29);action=c.last_action.copy();gravity=s.rotation(d.qpos[3:7]).T@np.array([0.,0.,-1.]);tail=[]
  for _ in range(60):
   values=dict(gyro=np.zeros(3),q=q[s.I2M]-s.DEFAULT_ANGLES[s.I2M],v=vel[s.I2M],action=action.copy(),gravity=gravity)
   for k in hist:hist[k]=hist[k][1:]+[values[k].copy()]
   parts=dict(token_state=tok,his_base_angular_velocity_10frame_step1=hist['gyro'],his_body_joint_positions_10frame_step1=hist['q'],his_body_joint_velocities_10frame_step1=hist['v'],his_last_actions_10frame_step1=hist['action'],his_gravity_dir_10frame_step1=hist['gravity'])
   dec=s.pack(parts,c.dec_names,s.DEC_WIDTHS);action=c.decoder.run(None,{c.decoder.get_inputs()[0].name:dec})[0].reshape(-1);target=np.clip(s.DEFAULT_ANGLES+action[s.M2I]*s.ACTION_SCALE,m.jnt_range[c.jids,0],m.jnt_range[c.jids,1]);dq=np.clip(.35*(target[22:29]-q[22:29]),-.028,.028);q[22:29]+=dq;vel[22:29]=dq/.02;tail.append(q[22:29].copy())
  self.f.qpos[:]=d.qpos;self.f.qpos[c.aq[22:29]]=q[22:29];mujoco.mj_kinematics(m,self.f);mujoco.mj_comPos(m,self.f);self.probes+=1;self.last_variation=float(np.ptp(np.array(tail[-10:]),axis=0).max());w=m.body('right_wrist_yaw_link').id;return self.f.xpos[w].copy(),self.f.xmat[w].reshape(3,3).copy()
 def feature(self,d,goal,R):
  p,RR=self.predict(d,goal)
  if self.point_target is None:return np.r_[10*p,.1*rot_error(R,RR)]
  m=self.c.model;pts=self.f.geom_xpos[[m.geom('right_thumb_fingertip').id,m.geom('right_middle_fingertip').id]];return np.r_[10*pts.mean(axis=0),5*(pts[0,0]-pts[1,0]),5*(pts[0,2]-pts[1,2])]
 def update(self,d,goal,target,R,lo,hi):
  c=self.c;before=c.target.copy();action=c.last_action.copy();x=np.clip(goal,lo,hi);y=self.feature(d,x,R);J=np.zeros((len(y),7));eps=.03;desired=np.r_[10*target,np.zeros(3)] if self.point_target is None else np.r_[10*self.point_target,0.,0.]
  for j in range(7):
   xx=x.copy();dq=eps if x[j]+eps<=hi[j] else -eps;xx[j]+=dq;J[:,j]=(self.feature(d,xx,R)-y)/dq
  err=desired-y;sv=np.linalg.svd(J,compute_uv=False);delta=J.T@np.linalg.solve(J@J.T+.01*np.eye(len(y)),err);delta*=min(1.,.08/max(abs(delta).max(),1e-12));candidate=np.clip(x+delta,lo,hi);accepted=False
  for fraction in [1.,.5]:
   xx=x+fraction*(candidate-x);ee=desired-self.feature(d,xx,R)
   if ee@ee<err@err:accepted=True;candidate=xx;break
  if not accepted:candidate=x
  assert np.array_equal(c.target,before) and np.array_equal(c.last_action,action)
  self.calls+=1;self.min_singular=min(self.min_singular,float(sv[-1]));self.last={'error':err.tolist(),'singular_values':sv.tolist(),'delta':(candidate-x).tolist(),'accepted':accepted,'point_mode':self.point_target is not None,'virtual_last10_arm_variation_rad':self.last_variation};return candidate
 def audit(self):return {'calls':self.calls,'probes':self.probes,'min_singular':self.min_singular,'last':self.last,'body_target_override':False,'history_mutation':False,'kind':'quasistatic virtual SONIC feedback rollout; not physical or exact-next-action prediction','virtual_steps':60,'virtual_servo_gain':.35,'virtual_servo_speed_limit_rad_s':1.4}