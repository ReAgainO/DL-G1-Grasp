from pathlib import Path
import json,copy,numpy as np,mujoco
from scipy.optimize import least_squares
import sonic_grasp as g
r=Path.cwd();out=r/'out/prepare18';out.mkdir();scene,*_=g.scene_and_cal(r,out,direct_table=True,table_front=.24,cube_x=.28,cube_y=-.118,cube_edge_mm=50.);m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m);j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];d.qpos[:3]=[-.06,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[qa[:29]]=g.neutral_body(m,g.s.DEFAULT_ANGLES,0);base=d.qpos.copy();w=m.body('right_wrist_yaw_link').id;lo=m.jnt_range[j[22:29],0]+.04;hi=m.jnt_range[j[22:29],1]-.04
plan=copy.deepcopy(json.load(open(r/'out/pose_plan_candidates16.json'))[0]);path=copy.deepcopy(json.load(open(r/'out/joint_waypoints16.json')));R=np.array(plan['wrist_R']);plan['wrist_target'][2]+=.0075;plan['grasp_center'][2]+=.0075
for vv in path['waypoints']:
 if vv['name'] not in ['PRE','GRASP','LIFT']:continue
 target=np.array(vv['wrist_p'])+np.array([0,0,.0075]);RR=np.array(vv['wrist_R']);seed=np.array(vv['arm_q'])
 def fun(q):
  d.qpos[:]=base;d.qpos[qa[22:29]]=q;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);return np.r_[100*(d.xpos[w]-target),g.rot_error(RR,d.xmat[w].reshape(3,3)),.001*(q-seed)]
 o=least_squares(fun,np.clip(seed,lo,hi),bounds=(lo,hi),max_nfev=180);fun(o.x);assert np.linalg.norm(d.xpos[w]-target)<.002;vv['wrist_p']=target.tolist();vv['arm_q']=o.x.tolist()
 if vv['name']=='GRASP':plan['arm_q']=o.x.tolist();plan['frozen_fit']['reference_arm']=o.x.tolist()
plan['cube_variant']='50mm calibration case; original35mm remains failed/unvalidated';path['grasp_plan']=plan;path['cube_variant']=plan['cube_variant'];(r/'out/pose_plan_candidates18.json').write_text(json.dumps([plan],indent=2));(r/'out/joint_waypoints18.json').write_text(json.dumps(path,indent=2));print('Prepared distinct50mm case, no physics success claim.')
