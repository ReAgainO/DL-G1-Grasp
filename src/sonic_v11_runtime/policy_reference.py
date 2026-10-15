"""Local inverse reference mapping through SONIC; never mutate policy actions/history.

Finite differences probe a frozen current observation. They only suggest the
next motion reference. The actual body command is always the normal next SONIC
encoder/decoder result, followed by the configured PD actuator adapter.
"""
import numpy as np,mujoco
import sonic_v11 as s
import source_physics_core as core

def features(m,d,flat):
 p=np.array([d.geom_xpos[m.geom(n).id] for n in core.PADS]);mid=(p[0]+p[1])*.5
 return np.r_[mid,p[0,2]-p[1,2],p[2,2]-p[1,2]] if flat else mid

class PolicyReference:
 def __init__(self,c):
  self.c=c;self.fk=mujoco.MjData(c.model);self.calls=0;self.probes=0;self.max_delta=0.;self.min_singular=1e9;self.last_diagnostic=None
  offset=0;self.position_offset=None
  for n in c.enc_names:
   if n=='motion_joint_positions_10frame_step5':self.position_offset=offset
   offset+=s.ENC_WIDTHS[n]
  assert self.position_offset is not None and c.dec_names[0]=='token_state'
 def predicted(self,d,action,hand,incremental=False):
  m=self.c.model;self.fk.qpos[:]=d.qpos
  target=s.DEFAULT_ANGLES+action[s.M2I]*s.ACTION_SCALE
  target=np.clip(target,m.jnt_range[self.c.jids,0],m.jnt_range[self.c.jids,1])
  if incremental:
   target[22:29]=np.clip(d.qpos[self.c.aq[22:29]]+target[22:29]-self.c.target[22:29],m.jnt_range[self.c.jids[22:29],0],m.jnt_range[self.c.jids[22:29],1])
  self.fk.qpos[self.c.aq[22:29]]=target[22:29]
  hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];self.fk.qpos[hq]=hand;mujoco.mj_forward(m,self.fk)
 def update(self,d,current_goal,prior,targetpos,hand,flat=False,weight=.03,incremental=False):
  c=self.c;m=c.model
  if c.last_encoder is None or c.last_decoder is None:raise ValueError('Need a real SONIC policy step first')
  if c.last_encoder[0,0]!=0:raise ValueError('Policy-aware reference supports G1 mode0 only')
  self.predicted(d,c.last_action,hand,incremental);baseline=features(m,self.fk,flat)
  J=np.zeros((len(baseline),7));eps=.03
  for j in range(7):
   encoder=c.last_encoder.copy();idx=s.M2I[22+j]
   addresses=self.position_offset+np.arange(10)*29+idx;epsj=eps
   limit=m.jnt_range[c.jids[22+j]]
   if encoder[0,addresses].max()+eps>limit[1]:epsj=-eps
   if encoder[0,addresses].min()+epsj<limit[0]:raise ValueError('No legal local finite-difference reference perturbation')
   for address in addresses:encoder[0,address]+=epsj
   token=c.encoder.run(None,{c.encoder.get_inputs()[0].name:encoder})[0].reshape(-1)
   decoder=c.last_decoder.copy();decoder[0,:64]=token
   action=c.decoder.run(None,{c.decoder.get_inputs()[0].name:decoder})[0].reshape(-1)
   self.predicted(d,action,hand,incremental);J[:,j]=(features(m,self.fk,flat)-baseline)/epsj;self.probes+=1
  self.fk.qpos[:]=d.qpos;hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];self.fk.qpos[hq]=hand;mujoco.mj_forward(m,self.fk)
  actual=features(m,self.fk,flat);desired=np.r_[targetpos,0.,0.] if flat else np.asarray(targetpos)
  error=desired-actual
  if flat:
   weights=np.array([1.,1.,1.,.5,.5]);J*=weights[:,None];error*=weights
  singular=np.linalg.svd(J,compute_uv=False);self.min_singular=min(self.min_singular,float(singular[-1]))
  inv=J.T@np.linalg.solve(J@J.T+.0002*np.eye(len(J)),np.eye(len(J)))
  delta=inv@error+weight*(np.eye(7)-inv@J)@(prior-current_goal)
  delta*=min(1,.06/max(abs(delta).max(),1e-12));self.max_delta=max(self.max_delta,float(abs(delta).max()));self.calls+=1
  self.last_diagnostic=dict(linearization='actual pose + decoded target increment; local unit servo response approximation' if incremental else 'absolute decoded target FK',singular_values=singular.tolist(),jacobian=J.tolist(),actual_features=actual.tolist(),predicted_features=baseline.tolist(),desired_features=desired.tolist(),delta_rad=delta.tolist(),reference_anchor_rad=np.asarray(current_goal).tolist(),decoded_motor_target_rad=c.target[22:29].tolist())
  lo=m.jnt_range[c.jids[22:29],0]+.02;hi=m.jnt_range[c.jids[22:29],1]-.02
  return np.clip(current_goal+delta,lo,hi)
 def audit(self):return dict(calls=self.calls,frozen_observation_probes=self.probes,max_reference_update_rad=self.max_delta,
                           min_effective_jacobian_singular_value=self.min_singular,
                           arm_output_override=False,policy_history_mutation_by_probes=False,reference_update_hz=5,last_diagnostic=self.last_diagnostic)
