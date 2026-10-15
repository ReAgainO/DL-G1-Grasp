from pathlib import Path
import json,numpy as np,mujoco
from motion_input import ArdyMotion
r=Path(__file__).resolve().parent;o=r/'out/native_ardy22'
motion=ArdyMotion(o/'generated_s42.npz',check_csv=o/'generated_s42.csv')
m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial16/scene.xml'));d=mujoco.MjData(m);base=np.load(r/'out/normal_trial16/trajectory.npz')['qpos'][0];ids=m.actuator_trnid[:29,0];qa=m.jnt_qposadr[ids];names=[m.joint(k).name for k in ids];order=[motion.joint_names.index(n) for n in names];w=m.body('right_wrist_yaw_link').id
p=json.loads((o/'planned_keyframes.json').read_text());records=[];poses=[];R=[];violations=[]
for frame,q in enumerate(motion.qpos):
 d.qpos[:]=base;d.qpos[:7]=q[:7];d.qpos[qa]=q[7:][order];mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);poses.append(d.xpos[w].copy());R.append(d.xmat[w].reshape(3,3).copy())
 violations.append(float(np.maximum(m.jnt_range[ids,0]-d.qpos[qa],d.qpos[qa]-m.jnt_range[ids,1]).max()))
for k,f in enumerate(p['frame_indices']):
 RM=R[f]@np.array(p['wrist_R'][k]).T;angle=np.arccos(np.clip((np.trace(RM)-1)/2,-1,1))
 records.append(dict(frame=f,planned_xyz=p['wrist_xyz'][k],decoded_fk_xyz=poses[f].tolist(),wrist_position_error_mm=float(np.linalg.norm(poses[f]-p['wrist_xyz'][k])*1000),wrist_orientation_error_deg=float(np.rad2deg(angle)),max_joint_limit_violation_rad=violations[f]))
res=dict(parity=motion.audit,keyframe_actual_robot_fk=records,all_frame_max_limit_violation_rad=max(violations),native_keyframes_are_not_hard_guarantees=True,physical_success=False)
(o/'decoded-fk-validation.json').write_text(json.dumps(res,indent=2));np.savez_compressed(o/'decoded-fk.npz',wrist_xyz=poses,wrist_R=R,body_joint_q=motion.qpos[:,7:],root_qpos=motion.qpos[:,:7],joint_limit_violation=violations)
print(json.dumps(res),flush=True)
