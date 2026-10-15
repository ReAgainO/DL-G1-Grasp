"""No physics steps: official teleop slot order, mutations and G1 regression."""
import json,importlib.util
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
root=Path(__file__).resolve().parent;m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m)
c=s.SonicV11(m);d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES;mujoco.mj_forward(m,d)
q=np.tile(s.DEFAULT_ANGLES,(10,1));v=np.zeros((10,29));r=np.tile([1.,0,0,0],(10,1));p=np.array([[.2,.1,.1],[.2,-.1,.1],[0,0,.6]]);o=np.tile([1.,0,0,0],(3,1))
tests=[]
def check(name,b):
 assert bool(b),name;tests.append(name)
a=c.step_teleop(d,q,v,r,p,o);enc=c.last_encoder.copy();token=c.last_token.copy()
check('mode_id1_padding_not_onehot',np.array_equal(enc[0,:4],[1,0,0,0]))
slots={};offset=0
for name in c.enc_names:
 width=s.ENC_WIDTHS[name];slots[name]=enc[0,offset:offset+width];offset+=width
check('g1_slots_zero',all(np.count_nonzero(slots[n])==0 for n in ['motion_joint_positions_10frame_step5','motion_joint_velocities_10frame_step5','motion_anchor_orientation_heading_10frame_step5']))
check('lowerbody_MuJoCo_leg_order',np.array_equal(slots['motion_joint_positions_lowerbody_10frame_step5'],q[:,:12].astype(np.float32).reshape(-1)))
check('left_right_head_position_order',np.array_equal(slots['vr_3point_local_target'],p.astype(np.float32).reshape(-1)))
check('wxyz_orientation_order',np.array_equal(slots['vr_3point_local_orn_target'],o.astype(np.float32).reshape(-1)))
check('unused_wrist_SMPL_slots_zero',all(np.count_nonzero(slots[n])==0 for n in ['smpl_joints_10frame_step1','smpl_anchor_orientation_heading_10frame_step1','motion_joint_positions_wrists_10frame_step1']))
fresh=s.SonicV11(m);b=fresh.step_teleop(d,q,v,r,p,o);check('cold_repeat_bitwise',np.array_equal(a,b))
changed=s.SonicV11(m);p2=p.copy();p2[1,0]+=.03;b=changed.step_teleop(d,q,v,r,p2,o)
check('right_target_consumed_by_encoder',not np.array_equal(enc,changed.last_encoder))
check('right_target_changes_token',not np.array_equal(token,changed.last_token))
check('right_target_changes_body_actions',not np.array_equal(a,b))
for name,P,O in [('shape',p[:2],o),('nan',p*np.nan,o),('nonunit',p,o*2)]:
 try:s.SonicV11(m).step_teleop(d,q,v,r,P,O)
 except ValueError:tests.append('reject_'+name)
 else:raise AssertionError(name)
spec=importlib.util.spec_from_file_location('wave1',root/'sonic_v11_wave1.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
oldc=old.SonicV11(m);newc=s.SonicV11(m)
old_a=oldc.step_policy(d,q,v,r);new_a=newc.step_policy(d,q,v,r)
check('G1_encoder_unchanged_bitwise',np.array_equal(oldc.last_encoder,newc.last_encoder))
check('G1_decoder_unchanged_bitwise',np.array_equal(oldc.last_decoder,newc.last_decoder))
check('G1_actions_unchanged_bitwise',np.array_equal(old_a,new_a))
out=root/'out/teleop-contract-tests.json';assert not out.exists()
result=dict(pass_count=len(tests),tests=tests,action_change_max=float(np.max(abs(a-b))),source_sha=s.sha(s.__file__),wave1_source_sha=s.sha(root/'sonic_v11_wave1.py'),models=c.model_stamp)
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
