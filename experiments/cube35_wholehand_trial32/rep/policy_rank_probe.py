from pathlib import Path
import numpy as np,mujoco,json
import sonic_v11 as s
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial03/scene.xml'));d=mujoco.MjData(m);a=np.load(r/'out/normal_trial03/trajectory.npz');d.qpos[:]=a['qpos'][-1];c=s.SonicV11(m);q=a['body_reference'][-1];future=np.tile(q,(10,1));fv=np.zeros_like(future);rr=np.tile([1.,0,0,0],(10,1))
for _ in range(11):c.step_policy(d,future,fv,rr)
base=c.last_encoder.copy();dec=c.last_decoder.copy();offset=0
for n in c.enc_names:
 if n=='motion_joint_positions_10frame_step5':posoff=offset
 offset+=s.ENC_WIDTHS[n]
def decode(enc):
 tok=c.encoder.run(None,{c.encoder.get_inputs()[0].name:enc})[0].reshape(-1);v=dec.copy();v[0,:64]=tok;return c.decoder.run(None,{c.decoder.get_inputs()[0].name:v})[0].reshape(-1)
baseline=decode(base);rows=[]
for jj in range(7):
 e=base.copy();e[0,posoff+np.arange(10)*29+s.M2I[22+jj]]+=.03;out=decode(e);diff=(out-baseline)[s.M2I[22:29]]*s.ACTION_SCALE[22:29]/.03
 rows.append(diff.tolist())
print('G1_RAW_JOINT_JAC_TRANSPOSE',json.dumps(rows))
# Test fixed observation slots alone to distinguish missing wiring from rank loss.
off=0
for n in c.enc_names:
 if n=='motion_joint_positions_wrists_10frame_step1':wr_off=off
 off+=s.ENC_WIDTHS[n]
rows=[]
for jj in range(6):
 e=base.copy();e[0,wr_off+np.arange(10)*6+jj]+=.03;out=decode(e);rows.append(((out-baseline)[s.M2I[22:29]]*s.ACTION_SCALE[22:29]/.03).tolist())
print('G1_WRIST_SLOT_JAC_TRANSPOSE',json.dumps(rows))
# Inspect teleop FK representation with the archived deploy offset convention.
f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[c.aq]=q;mujoco.mj_kinematics(m,f);mujoco.mj_comPos(m,f);rootR=s.rotation(d.qpos[3:7]);positions=[];quats=[]
for bn,ofs in [('left_wrist_yaw_link',[.18,-.025,0]),('right_wrist_yaw_link',[.18,.025,0]),('torso_link',[0,0,.35])]:
 b=m.body(bn).id;R=f.xmat[b].reshape(3,3);positions.append(rootR.T@(f.xpos[b]+R@ofs-d.qpos[:3]));quat=np.zeros(4);mujoco.mju_mat2Quat(quat,(rootR.T@R).flatten());quats.append(quat)
c.step_teleop(d,future,fv,rr,np.array(positions),np.array(quats));base=c.last_encoder.copy();dec=c.last_decoder.copy();baseline=decode(base);offset=0
for n in c.enc_names:
 if n=='vr_3point_local_target':vp=offset
 if n=='vr_3point_local_orn_target':vo=offset
 offset+=s.ENC_WIDTHS[n]
rows=[]
for jj in range(6):
 e=base.copy()
 if jj<3:e[0,vp+3+jj]+=.01
 else:
  qq=e[0,vo+4:vo+8].copy();dq=np.zeros(4);axis=np.zeros(3);axis[jj-3]=1;mujoco.mju_axisAngle2Quat(dq,axis,.01);new=np.zeros(4);mujoco.mju_mulQuat(new,dq,qq);e[0,vo+4:vo+8]=new
 out=decode(e);rows.append(((out-baseline)[s.M2I[22:29]]*s.ACTION_SCALE[22:29]/.01).tolist())
print('TELEOP_RAW_JAC_TRANSPOSE',json.dumps(rows));print('TELEOP_SINGULAR',np.linalg.svd(np.array(rows).T,compute_uv=False));print('TELEOP_TARGET',c.target[22:29]);print('DESIRED',q[22:29])