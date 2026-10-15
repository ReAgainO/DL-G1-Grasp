"""Native ARDY generation with passive hybrid-token trace and paired decoded output."""
from pathlib import Path
import json,time,hashlib,types
import numpy as np,torch
torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
from ardy.skeleton import G1Skeleton34
from ardy.exports.mujoco import MujocoQposConverter
from ardy.geometry import axis_angle_to_matrix,matrix_to_axis_angle
from ardy.constraints import load_constraints_lst
from ardy.model import load_model
from ardy.motion_rep.tools import length_to_mask
from ardy.tools import seed_everything,to_numpy
from ardy_encoder_local import build_encoder,CachedEncoder
r=Path(__file__).resolve().parent;o=r/'out/native_ardy22';inp=o/'planned_keyframes.json';p=json.loads(inp.read_text());sk=G1Skeleton34();conv=MujocoQposConverter(sk)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for z in iter(lambda:f.read(1048576),b''):h.update(z)
 return h.hexdigest()
C=conv.mujoco_to_ardy_matrix;N=len(p['frame_indices'])
lr=torch.eye(3)[None,None].repeat(N,sk.nbjoints,1,1);rp=torch.tensor(p['root_xyz'],dtype=torch.float32)@C.T
qdict={n:torch.tensor(p['body_joint_q'],dtype=torch.float32)[:,i] for i,n in enumerate(p['body_joint_names'])}
expected=torch.zeros(N,36);expected[:,:3]=torch.tensor(p['root_xyz']);expected[:,3:7]=torch.tensor(p['root_wxyz'])
from scipy.spatial.transform import Rotation
for frame,q in enumerate(p['root_wxyz']):
 RM=torch.tensor(Rotation.from_quat(q,scalar_first=True).as_matrix(),dtype=torch.float32);lr[frame,0]=C@RM@C.T
for i,ai in enumerate(conv._mujoco_indices_to_ardy_indices.tolist()):
 name=conv._mujoco_joint_including_root_list[i+1].replace('_skel','_joint');q=qdict[name];expected[:,7+i]=q
 ax=conv._mujoco_joint_axis_values_ardy_space[i]
 lr[:,ai]=conv._rot_offsets_f2q[ai].T@axis_angle_to_matrix(q[:,None]*ax[None])
back=conv.dict_to_qpos(dict(local_rot_mats=lr,root_positions=rp));back=np.asarray(back).reshape(N,36)
err=float(np.max(abs(back-expected.numpy())));assert err<2e-6,err
_,gp,gr=sk.fk(lr,rp);wi=sk.bone_order_names.index('right_wrist_yaw_skel');wrist=(gp[:,wi]@C).numpy();fkerr=np.linalg.norm(wrist-np.array(p['wrist_xyz']),axis=1)
# Body q roundtrip and physical wrist FK parity are separate checks.
assert fkerr.max()<.006,fkerr.tolist()
aa=matrix_to_axis_angle(lr).numpy().tolist();root=rp.numpy().tolist();root2=gp[:,sk.root_idx][:,[0,2]].numpy().tolist()
key=dict(frame_indices=p['frame_indices'],local_joints_rot=aa,root_positions=root,root_2d=root2)
footlr=lr[:1].repeat(200,1,1,1);footrp=rp[:1].repeat(200,1);_,fgp,_=sk.fk(footlr,footrp)
cons=[dict(type='fullbody',**key),dict(type='end-effector',joint_names=['RightHand','LeftHand','LeftFoot','RightFoot','Hips'],**key),dict(type='end-effector',joint_names=['LeftFoot','RightFoot','Hips'],frame_indices=list(range(200)),local_joints_rot=matrix_to_axis_angle(footlr).numpy().tolist(),root_positions=footrp.numpy().tolist(),root_2d=fgp[:,sk.root_idx][:,[0,2]].numpy().tolist())]
cp=o/'constraints.json';cp.write_text(json.dumps(cons,indent=2))
(o/'constraint-compiler-validation.json').write_text(json.dumps(dict(qpos_roundtrip_max_abs=err,physical_wrist_fk_error_mm=(fkerr*1000).tolist(),frame_indices=p['frame_indices'],C_mujoco_to_ardy=C.tolist(),csv_quaternion='wxyz',keyframe_source_sha256=sha(inp),constraints_sha256=sha(cp),geometry_keyframes_not_physical_success=True),indent=2))
print('COMPILED',err,(fkerr*1000).tolist(),flush=True)
tic=time.monotonic();enc=CachedEncoder(build_encoder('stacked','/home/group4/group4_dasc7606c/weights/ardy_textenc','cpu'))
modelname='ARDY-G1-RP-25FPS-Horizon52';weights=Path('/home/group4/group4_dasc7606c/weights/ardy_ckpt');model=load_model(modelname,device='cpu',text_encoder=enc,checkpoints_dir=str(weights))
assert model.motion_rep.fps==25
traces={};meta=[];orig=model._recenter_history
def capture(*args,**kwargs):
 i=len(meta);h=args[0];result=orig(*args,**kwargs)
 traces['window_%02d_before'%i]=h.detach().cpu().numpy().copy();traces['window_%02d_requantized'%i]=result[0].detach().cpu().numpy().copy();traces['window_%02d_center_pos'%i]=result[1].detach().cpu().numpy().copy()
 meta.append(dict(window=i,shape=list(h.shape),dtype=str(h.dtype),requantize=bool(kwargs.get('requantize',False)),center_frame_index=to_numpy(args[1]).tolist()))
 return result
model._recenter_history=capture
for name in ['get_explicit_motion_from_hybrid','get_explicit_motion_from_hybrid_autoregressive']:
 if not hasattr(model.hybrid,name):continue
 original=getattr(model.hybrid,name)
 def wrapped(*args,_fn=original,_name=name,**kwargs):
  key=_name+'_%02d'%len([k for k in traces if k.startswith(_name)]);traces[key]=args[0].detach().cpu().numpy().copy()
  return _fn(*args,**kwargs)
 setattr(model.hybrid,name,wrapped)
lst=load_constraints_lst(str(cp),model.skeleton);lengths=torch.tensor([200]);observed,mask=model.motion_rep.create_conditions_from_constraints_batched(lst,lengths,to_normalize=True,device='cpu')
seed_everything(42);prompt='A humanoid robot stands balanced, reaches its right hand down to a small cube on a table, grasps the cube, and raises its right hand while keeping both feet planted.'
motion=model([prompt],200,num_denoising_steps=10,pad_mask=length_to_mask(lengths),first_heading_angle=torch.zeros(1),motion_mask=mask,observed_motion=observed,cfg_weight=(2.,2.),crop_history_length=196,progress_bar=lambda indices: indices)
output=to_numpy(model.motion_rep.inverse(motion,is_normalized=True));qpos=np.asarray(conv.dict_to_qpos(output,'cpu')).reshape(200,36);arrays={k:(np.asarray(v)[0] if np.asarray(v).ndim and np.asarray(v).shape[0]==1 else np.asarray(v)) for k,v in output.items()};arrays.update(fps=np.asarray(25),text=np.asarray(prompt));np.savez_compressed(o/'generated_s42.npz',**arrays);np.savetxt(o/'generated_s42.csv',qpos,delimiter=',')
traces['returned_normalized_explicit_motion']=to_numpy(motion);traces['consumed_observed_motion']=to_numpy(observed);traces['consumed_motion_mask']=to_numpy(mask);np.savez_compressed(o/'hybrid_trace_s42.npz',**traces)
decoded_fk=arrays['global_joints_positions'][:,wi]@C.numpy() if 'global_joints_positions' in arrays else None
qdiff=np.max(abs(qpos[p['frame_indices']]-expected.numpy()),axis=1)
manifest=dict(task='20261008-202654-codex-182c4568',native_generation=True,ardy_source='/data/group4/20261005-222503-codex-a8d69b27/src/ardy',prompt=prompt,seed=42,frames=200,fps=25,diffusion_steps=10,torch=torch.__version__,model=modelname,device='cpu',threads=2,text_encoder_mode='stacked LLM2Vec MNTP merged + supervised adapter; original local probe method',keyframe_qpos_max_abs_error=qdiff.tolist(),token_trace_meta=meta,trace_definition='Actual normalized hybrid root/body representation before and after native recenter(requantize=True), and exact native hybrid decoder input. Not SONIC token IDs.',file_sha={f.name:sha(f) for f in [inp,cp,o/'generated_s42.npz',o/'generated_s42.csv',o/'hybrid_trace_s42.npz',Path(__file__),r/'ardy_encoder_local.py']},elapsed_s=time.monotonic()-tic,physical_grasp_success=False,active_in_controller=False)
# Hash only the resolved ARDY model directory; text-encoder paths and configs
# are recorded without claiming full weight hashes.
mdir=weights/modelname
manifest['ardy_model_files']=[dict(path=str(f),size=f.stat().st_size,sha256=sha(f)) for f in mdir.rglob('*') if f.is_file()]
(o/'generation-manifest.json').write_text(json.dumps(manifest,indent=2));print('NATIVE_RESULT',json.dumps(manifest),flush=True)
