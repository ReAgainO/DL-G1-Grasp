"""Strict official SONIC v1.1 CPU adapter. No body/arm control override.

Ported observation layout from the archived official YAML/C++ gatherers.
G1 mode id is 0 followed by three zero padding entries (not one-hot).
"""
from collections import deque
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import mujoco

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'pydeps'))
import onnxruntime as ort
import yaml
sys.path.insert(0,str(ROOT/'official_refs'))
from sonic_action_adapter import DEFAULT_ANGLES, I2M, M2I, ACTION_SCALE, KP, KD

ENC_WIDTHS={
 'encoder_mode_4':4,
 'motion_joint_positions_10frame_step5':290,
 'motion_joint_velocities_10frame_step5':290,
 'motion_anchor_orientation_heading_10frame_step5':60,
 'motion_anchor_orientation_heading':6,
 'motion_joint_positions_lowerbody_10frame_step5':120,
 'motion_joint_velocities_lowerbody_10frame_step5':120,
 'vr_3point_local_target':9,
 'vr_3point_local_orn_target':12,
 'smpl_joints_10frame_step1':720,
 'smpl_anchor_orientation_heading_10frame_step1':60,
 'motion_joint_positions_wrists_10frame_step1':60,
}
DEC_WIDTHS={
 'token_state':64,
 'his_base_angular_velocity_10frame_step1':30,
 'his_body_joint_positions_10frame_step1':290,
 'his_body_joint_velocities_10frame_step1':290,
 'his_last_actions_10frame_step1':290,
 'his_gravity_dir_10frame_step1':30,
}
G1_REQUIRED={'encoder_mode_4','motion_joint_positions_10frame_step5',
             'motion_joint_velocities_10frame_step5','motion_anchor_orientation_heading_10frame_step5'}

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''): h.update(b)
 return h.hexdigest()

def rotation(q):
 a=np.zeros(9);mujoco.mju_quat2Mat(a,np.asarray(q,dtype=np.float64));return a.reshape(3,3)

def heading(q):
 w,x,y,z=q;return np.arctan2(2*(w*z+x*y),1-2*(y*y+z*z))

def pack(parts,names,widths):
 assert set(names)==set(widths), 'Slot name drift'
 arrays=[]
 for name in names:
  a=np.asarray(parts[name],dtype=np.float32).reshape(-1)
  if a.size!=widths[name] or not np.isfinite(a).all():raise ValueError('Invalid slot '+name)
  arrays.append(a)
 return np.concatenate(arrays)[None]

class SonicV11:
 def __init__(self, model):
  self.model=model
  self.jids=np.asarray(model.actuator_trnid[:29,0],dtype=int)
  self.aq=model.jnt_qposadr[self.jids];self.av=model.jnt_dofadr[self.jids]
  assert model.nu==43 and model.nq==57 and model.nv==55
  cfg=yaml.safe_load((ROOT/'sonic_v11/observation_config.yaml').read_text())
  self.teleop_cfg=next(x for x in cfg['encoder']['encoder_modes'] if x['name']=='teleop')
  self.enc_names=[x['name'] for x in cfg['encoder']['encoder_observations'] if x['enabled']]
  self.dec_names=[x['name'] for x in cfg['observations'] if x['enabled']]
  g1=next(x for x in cfg['encoder']['encoder_modes'] if x['name']=='g1')
  assert g1['mode_id']==0 and set(g1['required_observations'])==G1_REQUIRED
  assert sum(ENC_WIDTHS[n] for n in self.enc_names)==1751
  assert sum(DEC_WIDTHS[n] for n in self.dec_names)==994
  opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
  opts.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
  self.encoder=ort.InferenceSession(str(ROOT/'sonic_v11/model_encoder.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
  self.decoder=ort.InferenceSession(str(ROOT/'sonic_v11/model_decoder.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
  for sess,width,outwidth in [(self.encoder,1751,64),(self.decoder,994,29)]:
   assert len(sess.get_inputs())==len(sess.get_outputs())==1
   assert sess.get_inputs()[0].shape==[1,width] and sess.get_outputs()[0].shape==[1,outwidth]
   assert sess.get_inputs()[0].type=='tensor(float)' and sess.get_providers()==['CPUExecutionProvider']
  self.last_action=np.zeros(29,np.float32)
  self.hist={key:deque(maxlen=10) for key in ['gyro','q','v','action','gravity']}
  initial={'gyro':np.zeros(3),'q':np.zeros(29),'v':np.zeros(29),'action':np.zeros(29),'gravity':np.array([0.,0.,-1.])}
  for key in self.hist:
   self.hist[key].extend([initial[key].copy() for _ in range(10)])
  self.calls=0;self.encoder_hashes=set();self.action_hashes=set()
  self.target=DEFAULT_ANGLES.copy()
  self.last_encoder=None;self.last_token=None;self.last_decoder=None
  self.mode_ids=set()
  self.model_stamp={name:sha(ROOT/'sonic_v11'/name) for name in ['model_encoder.onnx','model_decoder.onnx','observation_config.yaml']}

 def step_policy(self,data,q_future,v_future,root_quat_future):
  q=np.asarray(q_future);v=np.asarray(v_future);r=np.asarray(root_quat_future)
  if q.shape!=(10,29) or v.shape!=(10,29) or r.shape!=(10,4):raise ValueError('Expect10 future frames at step5,50Hz')
  if not np.isfinite(q).all() or not np.isfinite(v).all() or not np.isfinite(r).all():raise ValueError('Nonfinite reference')
  if np.max(abs(np.linalg.norm(r,axis=1)-1))>1e-6:raise ValueError('Reference quaternion not unit')
  yaw=heading(data.qpos[3:7]);c,s=np.cos(yaw),np.sin(yaw)
  inv_heading=np.array([[c,s,0],[-s,c,0],[0,0,1]])
  orientations=np.array([(inv_heading@rotation(x))[:,:2].reshape(-1) for x in r])
  parts={n:np.zeros(w,dtype=np.float32) for n,w in ENC_WIDTHS.items()}
  parts.update(encoder_mode_4=np.zeros(4),motion_joint_positions_10frame_step5=q[:,I2M],
               motion_joint_velocities_10frame_step5=v[:,I2M],motion_anchor_orientation_heading_10frame_step5=orientations)
  enc=pack(parts,self.enc_names,ENC_WIDTHS)
  self.mode_ids.add(0)
  return self._decode(data,enc)

 def step_teleop(self,data,q_future,v_future,root_quat_future,local_positions,local_quaternions):
  """Official teleop mode1: left wrist/right wrist/head, root-local wxyz.

  Caller must apply official point offsets before root normalization.
  Lower-body slot uses MuJoCo leg order (official gatherer subset), NOT the
  interleaved Isaac order; all G1/SMPL slots remain zero in this mode.
  """
  q=np.asarray(q_future);v=np.asarray(v_future);r=np.asarray(root_quat_future)
  p=np.asarray(local_positions);o=np.asarray(local_quaternions)
  if q.shape!=(10,29) or v.shape!=(10,29) or r.shape!=(10,4) or p.shape!=(3,3) or o.shape!=(3,4):raise ValueError('Teleop reference shapes')
  if not all(np.isfinite(x).all() for x in [q,v,r,p,o]):raise ValueError('Nonfinite teleop reference')
  if max(np.max(abs(np.linalg.norm(r,axis=1)-1)),np.max(abs(np.linalg.norm(o,axis=1)-1)))>1e-6:raise ValueError('Nonunit teleop quaternion')
  teleop=self.teleop_cfg
  required={'encoder_mode_4','motion_joint_positions_lowerbody_10frame_step5','motion_joint_velocities_lowerbody_10frame_step5',
            'vr_3point_local_target','vr_3point_local_orn_target','motion_anchor_orientation_heading'}
  assert teleop['mode_id']==1 and set(teleop['required_observations'])==required
  yaw=heading(data.qpos[3:7]);c,s=np.cos(yaw),np.sin(yaw);inv_heading=np.array([[c,s,0],[-s,c,0],[0,0,1]])
  parts={n:np.zeros(w,dtype=np.float32) for n,w in ENC_WIDTHS.items()}
  parts.update(encoder_mode_4=np.array([1.,0,0,0]),motion_joint_positions_lowerbody_10frame_step5=q[:,:12],
               motion_joint_velocities_lowerbody_10frame_step5=v[:,:12],motion_anchor_orientation_heading=(inv_heading@rotation(r[0]))[:,:2].reshape(-1),
               vr_3point_local_target=p,vr_3point_local_orn_target=o)
  self.mode_ids.add(1)
  return self._decode(data,pack(parts,self.enc_names,ENC_WIDTHS))

 def _decode(self,data,enc):
  token=self.encoder.run(None,{self.encoder.get_inputs()[0].name:enc})[0].reshape(-1)
  values=dict(gyro=data.qvel[3:6].copy(),q=data.qpos[self.aq][I2M]-DEFAULT_ANGLES[I2M],
              v=data.qvel[self.av][I2M].copy(),action=self.last_action.copy(),
              gravity=rotation(data.qpos[3:7]).T@np.array([0.,0.,-1.]))
  for key in self.hist:self.hist[key].append(values[key])
  parts=dict(token_state=token,his_base_angular_velocity_10frame_step1=np.asarray(self.hist['gyro']),
             his_body_joint_positions_10frame_step1=np.asarray(self.hist['q']),
             his_body_joint_velocities_10frame_step1=np.asarray(self.hist['v']),
             his_last_actions_10frame_step1=np.asarray(self.hist['action']),
             his_gravity_dir_10frame_step1=np.asarray(self.hist['gravity']))
  dec=pack(parts,self.dec_names,DEC_WIDTHS)
  action=self.decoder.run(None,{self.decoder.get_inputs()[0].name:dec})[0].reshape(-1)
  if action.shape!=(29,) or not np.isfinite(action).all():raise RuntimeError('Invalid SONIC action')
  self.target=DEFAULT_ANGLES+action[M2I]*ACTION_SCALE
  self.target=np.clip(self.target,self.model.jnt_range[self.jids,0],self.model.jnt_range[self.jids,1])
  self.last_action=action.copy();self.calls+=1
  self.encoder_hashes.add(hashlib.sha256(enc.tobytes()).hexdigest())
  self.action_hashes.add(hashlib.sha256(action.tobytes()).hexdigest())
  self.last_encoder=enc;self.last_decoder=dec;self.last_token=token
  return action

 def torques(self,data):
  tau=KP*(self.target-data.qpos[self.aq])-KD*data.qvel[self.av]
  return np.clip(tau,self.model.actuator_ctrlrange[:29,0],self.model.actuator_ctrlrange[:29,1])

 def audit(self):
  return dict(ort_version=ort.__version__,models=self.model_stamp,encoder_slots=[dict(name=n,width=ENC_WIDTHS[n]) for n in self.enc_names],
              decoder_slots=[dict(name=n,width=DEC_WIDTHS[n]) for n in self.dec_names],policy_calls=self.calls,
              unique_encoder_inputs=len(self.encoder_hashes),unique_actions=len(self.action_hashes),
              body_action_source='official SONIC v1.1 ONNX; zero arm target overrides',mode_ids=sorted(self.mode_ids))
