import numpy as np,mujoco,json
from pathlib import Path
import sonic_v11 as s
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial05/scene.xml'));d=mujoco.MjData(m);c=s.SonicV11(m);d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES
cases=json.load(open(r/'out/joint_waypoints05.json'))['waypoints'];cases+=[{'name':'FIT_INPUT','arm_q':json.load(open(r/'out/pose_plan_candidates05.json'))[0]['frozen_fit']['reference_arm']}];records=[]
for pp in cases:
 q=s.DEFAULT_ANGLES.copy();q[22:29]=pp['arm_q'];d.qpos[c.aq]=s.DEFAULT_ANGLES;d.qvel[:]=0;cc=s.SonicV11(m);last=[]
 for k in range(100):
  cc.step_policy(d,np.tile(q,(10,1)),np.zeros((10,29)),np.tile([1.,0,0,0],(10,1)));delta=np.clip(.35*(cc.target[22:29]-d.qpos[c.aq[22:29]]),-.028,.028);d.qpos[c.aq[22:29]]+=delta;d.qvel[cc.av[22:29]]=delta/.02;last.append(cc.target[22:29].copy())
 mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);w=m.body('right_wrist_yaw_link').id;rec={'name':pp['name'],'reference':q[22:29].tolist(),'arm':d.qpos[cc.aq[22:29]].tolist(),'wrist':d.xpos[w].tolist(),'wrist_R':d.xmat[w].reshape(3,3).tolist(),'last20_command_variation_rad':float(np.ptp(np.array(last[-20:]),axis=0).max()),'last_approach_to_target_rad':float(abs(cc.target[22:29]-d.qpos[cc.aq[22:29]]).max())};print(json.dumps(rec),flush=True);records.append(rec)
(r/'out/steady_sonic_pose_probe09.json').write_text(json.dumps(records,indent=2))