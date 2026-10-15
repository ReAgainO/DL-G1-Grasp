"""Quasistatic SONIC feedback rollout for input-side task-point adjustment.
No real state/target/history writes; virtual joint follower is an approximation.
"""
import numpy as np,mujoco
import sonic_v11 as s
from mesh_contact import FingerSurfaces
from task_plan import rot_error
class MeshTokenReference:
 def __init__(self,c):
  self.surfaces=FingerSurfaces(c.model);self.c=c;self.f=mujoco.MjData(c.model);self.calls=0;self.probes=0;self.last=None;self.min_singular=1e9;self.point_target=None;self.bodies=[c.model.body('right_'+x+'_link').id for x in ['shoulder_pitch','shoulder_roll','shoulder_yaw','elbow','wrist_roll','wrist_pitch','wrist_yaw']];self.bodies += [i for i in range(c.model.nbody) if (c.model.body(i).name or '').startswith('right_hand_')];self.robot={c.model.body('pelvis').id};
  for i in range(1,c.model.nbody):
   if int(c.model.body_parentid[i]) in self.robot:self.robot.add(i)
  self.search_step=.08;off=0
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
  m=self.c.model;cube=m.body('red_cube').id;cg=m.geom('red_cube_geom').id;pts=self.surfaces.points(self.f,d.xpos[cube],d.xmat[cube].reshape(3,3),m.geom_size[cg,0],.012);return np.r_[10*pts.mean(axis=0),5*(pts[0,0]-pts[1,0]),5*(pts[0,2]-pts[1,2])]
 def geometric_penalty(self):
  m=self.c.model;f=self.f;pen=np.zeros(len(self.bodies)+1);table=m.geom('table_top').id;mujoco.mj_collision(m,f)
  for cx in f.contact[:f.ncon]:
   b1,b2=int(m.geom_bodyid[cx.geom1]),int(m.geom_bodyid[cx.geom2])
   if b1 in self.robot and b2 in self.robot:
    for bb in [b1,b2]:
     if bb in self.bodies:pen[self.bodies.index(bb)]=max(pen[self.bodies.index(bb)],max(0.,-cx.dist))
   if table in [cx.geom1,cx.geom2] and (b1 in self.robot or b2 in self.robot):pen[-1]=max(pen[-1],max(0.,-cx.dist))
  return 300*pen
 def objective(self,d,x,R,desired):
  yy=self.feature(d,x,R);ee=desired-yy;pen=self.geometric_penalty();return float(ee@ee+pen@pen)
 def update(self,d,goal,target,R,lo,hi):
  c=self.c;before=c.target.copy();action=c.last_action.copy();x=np.clip(goal,lo,hi);desired=np.r_[10*target,np.zeros(3)] if self.point_target is None else np.r_[10*self.point_target,0.,0.]
  y=self.feature(d,x,R);pen=self.geometric_penalty();basecost=float((desired-y)@(desired-y)+pen@pen);bestcost=basecost;candidate=x.copy();accepted=False;tried=0
  for j in [0,1,2,3,5,6]:
   for sign in [-1.,1.]:
    xx=x.copy();xx[j]=np.clip(xx[j]+sign*self.search_step,lo[j],hi[j])
    if np.array_equal(xx,x):continue
    cost=self.objective(d,xx,R,desired);tried+=1
    if cost<bestcost-1e-8:bestcost=cost;candidate=xx;accepted=True
  self.search_step=.08 if accepted else min(.20,self.search_step*1.5)
  assert np.array_equal(c.target,before) and np.array_equal(c.last_action,action)
  self.calls+=1;self.last={'error':(desired-y).tolist(),'baseline_cost':basecost,'best_cost':bestcost,'delta':(candidate-x).tolist(),'accepted':accepted,'point_mode':self.point_target is not None,'virtual_last10_arm_variation_rad':self.last_variation,'proposals':tried,'next_search_step':self.search_step};return candidate
 def audit(self):return {'calls':self.calls,'probes':self.probes,'min_singular':None,'last':self.last,'body_target_override':False,'history_mutation':False,'kind':'discrete SONIC reference search using actual compiled mesh closest surfaces plus self/table penalties','virtual_steps':60,'virtual_servo_gain':.35,'virtual_servo_speed_limit_rad_s':1.4}