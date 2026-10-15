import json,numpy as np,mujoco,time
from pathlib import Path
from scipy.optimize import least_squares
import sonic_v11 as s
from goal_pose_policy import GoalPoseReference
from task_plan import rot_error
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial04/scene.xml'));d=mujoco.MjData(m);a=np.load(r/'out/normal_trial04/trajectory.npz');d.qpos[:]=a['qpos'][-1];c=s.SonicV11(m);ref=a['body_reference'][-1];future=np.tile(ref,(10,1));v=np.zeros_like(future);rr=np.tile([1.,0,0,0],(10,1))
for _ in range(15):c.step_policy(d,future,v,rr)
p=GoalPoseReference(c);j=c.jids[22:29];lo=m.jnt_range[j,0]+.006;hi=m.jnt_range[j,1]-.006;wp=json.load(open(r/'out/joint_waypoints_trial03.json'))['waypoints'];result=[]
for w in [x for x in wp if x['name'] in ['PRE','GRASP']]:
 target=np.array(w['wrist_p']);R=np.array(w['wrist_R']);best=None
 for seed in [ref[22:29],np.array(w['arm_q'])]:
  tic=time.monotonic()
  def f(q):
   pp,RR=p.predict(d,q);return np.r_[10*(pp-target),rot_error(R,RR)]
  o=least_squares(f,np.clip(seed,lo,hi),bounds=(lo,hi),diff_step=.01,max_nfev=90,ftol=1e-5,xtol=1e-5,gtol=1e-5);pp,RR=p.predict(d,o.x)
  rr={'name':w['name'],'cost':float(o.cost),'qref':o.x.tolist(),'position_error_mm':float(np.linalg.norm(pp-target)*1000),'angle_error_deg':float(np.rad2deg(np.linalg.norm(rot_error(R,RR)))),'nfev':o.nfev,'success':bool(o.success),'wall_s':time.monotonic()-tic};print(json.dumps(rr),flush=True)
  if best is None or rr['cost']<best['cost']:best=rr
 result.append(best)
(r/'out/frozen_goal_fit05.json').write_text(json.dumps(result,indent=2))