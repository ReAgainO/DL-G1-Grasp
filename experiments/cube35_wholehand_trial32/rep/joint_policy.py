"""Inverse only the reference. Frozen SONIC probes never become actuator commands."""
import numpy as np
import sonic_v11 as s
class JointPolicyReference:
 def __init__(self,c):
  self.c=c;self.calls=0;self.probes=0;self.last=None;self.min_singular=1e9;off=0
  for n in c.enc_names:
   if n=='motion_joint_positions_10frame_step5':self.offset=off
   off+=s.ENC_WIDTHS[n]
 def q(self,a):
  c=self.c;return np.clip(s.DEFAULT_ANGLES+a[s.M2I]*s.ACTION_SCALE,c.model.jnt_range[c.jids,0],c.model.jnt_range[c.jids,1])[22:29]
 def update(self,d,reference,desired,lo,hi):
  c=self.c;before=c.target.copy();action=c.last_action.copy();q0=self.q(action);J=np.zeros((7,7));eps=.025
  for j in range(7):
   enc=c.last_encoder.copy();idx=self.offset+np.arange(10)*29+s.M2I[22+j];dq=eps
   if enc[0,idx].max()+dq>hi[j]:dq=-eps
   if enc[0,idx].min()+dq<lo[j]:continue
   enc[0,idx]+=dq;tok=c.encoder.run(None,{c.encoder.get_inputs()[0].name:enc})[0].reshape(-1);dec=c.last_decoder.copy();dec[0,:64]=tok
   a=c.decoder.run(None,{c.decoder.get_inputs()[0].name:dec})[0].reshape(-1);J[:,j]=(self.q(a)-q0)/dq;self.probes+=1
  err=desired-q0+np.clip(.25*(desired-d.qpos[c.aq[22:29]]),-.04,.04);sv=np.linalg.svd(J,compute_uv=False)
  delta=J.T@np.linalg.solve(J@J.T+.005*np.eye(7),err);delta*=min(1.,.12/max(abs(delta).max(),1e-12))
  assert np.array_equal(c.target,before) and np.array_equal(c.last_action,action)
  self.calls+=1;self.min_singular=min(self.min_singular,float(sv[-1]));self.last={'error':err.tolist(),'singular_values':sv.tolist(),'delta':delta.tolist()}
  return np.clip(reference+delta,lo,hi)
 def audit(self):return {'calls':self.calls,'probes':self.probes,'min_singular':self.min_singular,'last':self.last,'body_target_override':False,'history_mutation':False,'kind':'frozen NN joint-reference Jacobian'}