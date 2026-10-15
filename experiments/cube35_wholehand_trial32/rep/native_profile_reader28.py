"""Attributed derived ARDY body reference reader, no model/physics state mutations."""
import json
from pathlib import Path
import numpy as np,mujoco
from sonic_v11 import sha
class NativeProfile28:
 def __init__(self,root):
  self.path=Path(root)/'out/native_profile28/profile.npz';self.manifest=json.loads(self.path.with_name('manifest.json').read_text());assert sha(self.path)==self.manifest['profile_sha256']
  z=np.load(self.path);self.q=np.array(z['body_q']);self.p=np.array(z['wrist_xyz']);self.R=np.array(z['wrist_R']);self.root_quat=np.array(z['root_quat']);self.fps=float(z['fps']);self.n=len(self.q);self.quats=[]
  for R in self.R:
   q=np.zeros(4);mujoco.mju_mat2Quat(q,R.reshape(-1));self.quats.append(q)
  self.quats=np.array(self.quats);self.samples=0
 @staticmethod
 def clock(phase,e):
  a,b,D={'SETTLE':(0.,0.,1.),'RAISE':(0.,1.2,12.),'APPROACH':(1.2,2.4,18.),'PRESHAPE':(2.4,2.4,1.),'ALIGN':(2.4,4.4,16.),'CLOSE':(4.4,5.,6.),'TEST_LIFT':(5.,5.784493215054924,4.),'LIFT':(5.784493215054924,7.96,12.),'HOLD':(7.96,7.96,1.),'RELEASE':(7.96,7.96,1.),'FINAL':(7.96,7.96,1.)}[phase]
  u=np.clip(e/D,0,1);k=u*u*u*(10-15*u+6*u*u);return a+(b-a)*k,float(k),a
 def sample(self,t):
  ts=np.atleast_1d(t);x=np.clip(ts*self.fps,0,self.n-1);i=x.astype(int);j=np.minimum(i+1,self.n-1);u=x-i
  q=(1-u[:,None])*self.q[i]+u[:,None]*self.q[j];p=(1-u[:,None])*self.p[i]+u[:,None]*self.p[j];R=[]
  for aa,bb,w in zip(self.quats[i],self.quats[j],u):
   if aa@bb<0:bb=-bb
   angle=np.arccos(np.clip(aa@bb,-1,1));qq=(1-w)*aa+w*bb if angle<1e-6 else (np.sin((1-w)*angle)*aa+np.sin(w*angle)*bb)/np.sin(angle);qq/=np.linalg.norm(qq);rr=np.zeros(9);mujoco.mju_quat2Mat(rr,qq);R.append(rr.reshape(3,3))
  self.samples+=len(ts);return q,p,np.array(R)
 def audit(self):return dict(active_reference_reader=True,sampled_rows=self.samples,profile_sha256=sha(self.path),source_native_sha256=self.manifest['source_native']['source_npz_sha256'],source_hybrid_trace_sha256=self.manifest['hybrid_trace_sha256'],kind=self.manifest['kind'],derived_not_native_generated=True,fallback_count=self.manifest['fallback_count'],raw_to_final_mean_abs_rad=self.manifest['raw_to_final_mean_abs_rad'],raw_to_final_max_rad=self.manifest['raw_to_final_max_rad'])
