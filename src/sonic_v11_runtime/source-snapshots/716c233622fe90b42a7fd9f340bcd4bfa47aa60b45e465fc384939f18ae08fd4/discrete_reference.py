"""Quantization-aware local search of INPUT reference; never command probe actions.

Every candidate passes through the unchanged official encoder and decoder using
a frozen real observation. Only a bounded reference shift is returned. Normal
next-step policy inference, C2 filtering and original effort limits still apply.
"""
import numpy as np
import mujoco
import sonic_v11 as s
import source_physics_core as core
from grasp_geometry import contact_frame


class DiscreteReference:
 def __init__(self,c):
  self.c=c;self.fk=mujoco.MjData(c.model);self.calls=0;self.probes=0
  self.zero_token_probes=0;self.duplicates=0;self.max_delta=0.;self.last_diagnostic=None
  self.rng=np.random.default_rng(6046);self.offset=4
  assert c.enc_names[:2]==['encoder_mode_4','motion_joint_positions_10frame_step5']
  assert c.dec_names[0]=='token_state'

 def feature(self,d,arm,hand,cube_R,opponent):
  m=self.c.model;self.fk.qpos[:]=d.qpos;self.fk.qpos[self.c.aq[22:29]]=arm
  hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];self.fk.qpos[hq]=hand
  mujoco.mj_forward(m,self.fk)
  pads=np.array([self.fk.geom_xpos[m.geom(n).id] for n in core.PADS])
  return np.r_[contact_frame(m,self.fk,cube_R,opponent=opponent),pads[0,2]-pads[1,2],pads[2,2]-pads[1,2]]

 def update(self,d,anchor,desired_q,prior,targetpos,hand,cube_R,opponent=1,incremental=True):
  c=self.c;m=c.model
  if c.last_encoder is None or c.last_encoder[0,0]!=0:raise ValueError('Real G1 policy step required')
  actual_q=d.qpos[c.aq[22:29]].copy();desired=np.r_[targetpos,0.,0.]
  lo=m.jnt_range[c.jids[22:29],0]+.04;hi=m.jnt_range[c.jids[22:29],1]-.04
  # Coarse legal probes cross FSQ cells; exact token equality is measured.
  directed=desired_q-actual_q;directed*=min(1.,.12/max(abs(directed).max(),1e-12))
  deltas=[np.zeros(7),directed,-directed]
  for j in range(7):
   axis=np.zeros(7);axis[j]=.12;deltas.extend([axis,-axis])
  for _ in range(6):
   delta=self.rng.normal(size=7);delta*=.12/max(abs(delta).max(),1e-12);deltas.append(delta)
  records=[];cache={};before_token=c.last_token.copy()
  for delta in deltas:
   delta=np.clip(anchor+delta,lo,hi)-anchor;enc=c.last_encoder.copy()
   for j in range(7):
    addresses=self.offset+np.arange(10)*29+s.M2I[22+j]
    # Reject candidates that would clip future samples: do not fake derivatives.
    if (enc[0,addresses]+delta[j]<lo[j]).any() or (enc[0,addresses]+delta[j]>hi[j]).any():break
    enc[0,addresses]+=delta[j]
   else:
    token=c.encoder.run(None,{c.encoder.get_inputs()[0].name:enc})[0].reshape(-1);self.probes+=1
    if np.array_equal(token,before_token):self.zero_token_probes+=1
    key=token.tobytes()
    if key in cache:action=cache[key];self.duplicates+=1
    else:
     dec=c.last_decoder.copy();dec[0,:64]=token
     action=c.decoder.run(None,{c.decoder.get_inputs()[0].name:dec})[0].reshape(-1);cache[key]=action
    motor=s.DEFAULT_ANGLES+action[s.M2I]*s.ACTION_SCALE
    predicted_q=motor[22:29]
    if incremental:predicted_q=actual_q+predicted_q-c.target[22:29]
    predicted_q=np.clip(predicted_q,lo,hi)
    feat=self.feature(d,predicted_q,hand,cube_R,opponent)
    error=(feat-desired)*np.array([1.,1.,1.,.7,.7])
    cost=float(error@error+.00005*np.sum((anchor+delta-prior)**2)+.00002*np.sum(delta**2))
    records.append((cost,delta.copy(),feat.copy(),motor[22:29].copy(),int(np.count_nonzero(token!=before_token))))
  if not records:raise RuntimeError('No legal encoder candidates')
  best=min(records,key=lambda r:r[0]);self.calls+=1;self.max_delta=max(self.max_delta,float(abs(best[1]).max()))
  self.last_diagnostic=dict(candidate_count=len(records),distinct_tokens=len(cache),chosen_cost=best[0],
   selected_reference_delta_rad=best[1].tolist(),predicted_features=best[2].tolist(),desired_features=desired.tolist(),
   candidate_decoded_motor_target_rad=best[3].tolist(),changed_token_components=best[4],
   actual_features=self.feature(d,actual_q,hand,cube_R,opponent).tolist(),incremental=incremental)
  return anchor+best[1]

 def audit(self):return dict(calls=self.calls,frozen_probes=self.probes,unchanged_token_probes=self.zero_token_probes,
  duplicate_tokens=self.duplicates,max_reference_update_rad=self.max_delta,reference_update_hz=5,
  quantization_aware=True,policy_history_mutation=False,arm_action_override=False,last_diagnostic=self.last_diagnostic)
