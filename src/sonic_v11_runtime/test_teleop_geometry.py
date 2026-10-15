import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
from motion_input import ArdyMotion
root=Path(__file__).resolve().parent;out=root/'out/teleop-fk-tests.json';assert not out.exists()
m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m);fk=mujoco.MjData(m);c=s.SonicV11(m)
d.qpos[:3]=[0,0,.78874];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES;mujoco.mj_forward(m,d)
motion=ArdyMotion(root/'src/original_motions/near_s42.npz');tokens=[];encoders=[]
for frame in [0,31]:
 ref=s.DEFAULT_ANGLES.copy();ref[22:29]=motion.qpos[frame,29:36];fk.qpos[:]=d.qpos;fk.qpos[c.aq]=ref;mujoco.mj_forward(m,fk)
 rootR=s.rotation(d.qpos[3:7]);positions=[];quats=[]
 for body,offset in [('left_wrist_yaw_link',[.18,-.025,0]),('right_wrist_yaw_link',[.18,.025,0]),('torso_link',[0,0,.35])]:
  b=m.body(body).id;R=fk.xmat[b].reshape(3,3);positions.append(rootR.T@(fk.xpos[b]+R@np.array(offset)-d.qpos[:3]));quat=np.zeros(4);mujoco.mju_mat2Quat(quat,(rootR.T@R).reshape(-1));quats.append(quat)
 before=d.qpos.copy();c.step_teleop(d,np.tile(ref,(10,1)),np.zeros((10,29)),np.tile([1.,0,0,0],(10,1)),np.array(positions),np.array(quats));assert np.array_equal(d.qpos,before)
 tokens.append(c.last_token.copy());encoders.append(c.last_encoder.copy());slots={};start=0
 for key in c.enc_names:slots[key]=c.last_encoder[0,start:start+s.ENC_WIDTHS[key]];start+=s.ENC_WIDTHS[key]
 assert slots['encoder_mode_4'].tolist()==[1.,0,0,0]
 assert not slots['motion_joint_positions_10frame_step5'].any() and not slots['motion_joint_velocities_10frame_step5'].any()
 assert np.allclose(slots['vr_3point_local_target'].reshape(3,3),positions)
 assert np.allclose(np.linalg.norm(slots['vr_3point_local_orn_target'].reshape(3,4),axis=1),1)
assert not np.array_equal(encoders[0],encoders[1]) and not np.array_equal(tokens[0],tokens[1])
r=dict(physical_steps=0,pass_count=6,tests=['FK from original native ARDY frames','correct mode1','G1 joint slots unused/zero','official offset and root-local VR positions','unit wxyz wrist quaternions','native frame change consumed by encoder token'],max_token_difference=float(abs(tokens[1]-tokens[0]).max()),motor_target_override=False)
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
