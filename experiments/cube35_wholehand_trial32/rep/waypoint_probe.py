import json,numpy as np,mujoco
from pathlib import Path
from scipy.optimize import least_squares
import sonic_grasp as g
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial02/scene.xml'));d=mujoco.MjData(m)
f=np.load(r/'out/normal_trial02/trajectory.npz');j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];lo=m.jnt_range[j[22:29],0]+.02;hi=m.jnt_range[j[22:29],1]-.02
ph=f['phase'];ix=np.where(ph=='RAISE')[0][0];d.qpos[:]=f['qpos'][ix];base=d.qpos.copy();mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);w=m.body('right_wrist_yaw_link').id;R=d.xmat[w].reshape(3,3).copy()
plan=json.load(open(r/'out/normal_trial02/result.json'))['selected_plan'];Gp=np.array(plan['wrist_target']);GR=np.array(plan['wrist_R']);records=[]
for n,p,T in [('raise_fixed',[.06,-.38,1.04],R),('raise_free',[.06,-.32,1.02],None),('approach',Gp+[-.08,0,.15],GR),('high_pre',Gp+[-.08,0,.08],GR),('pre4',Gp+[-.08,0,.04],GR),('lift10',Gp+[0,0,.1],GR),('above4',Gp+[0,0,.04],GR),('pre',Gp+[-.08,0,0],GR),('grasp',Gp,GR)]:
 best=None
 for seed in [base[qa[22:29]],np.asarray(plan['arm_q']),np.array([-.8,-.2,0,1.3,0,.2,0])]:
  def fun(q):
   d.qpos[:]=base;d.qpos[qa[22:29]]=q;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
   return np.r_[30*(d.xpos[w]-p),g.rot_error(T,d.xmat[w].reshape(3,3)) if T is not None else .02*(q-seed)]
  o=least_squares(fun,np.clip(seed,lo,hi),bounds=(lo,hi),max_nfev=150);fun(o.x);err=np.linalg.norm(d.xpos[w]-p);er=np.linalg.norm(g.rot_error(T,d.xmat[w].reshape(3,3))) if T is not None else 0
  rec={'name':n,'q':o.x.tolist(),'target':np.asarray(p).tolist(),'R':d.xmat[w].reshape(3,3).tolist(),'pos_error_mm':err*1e3,'rerror_deg':np.rad2deg(er)}
  if best is None or err+er/30<best['pos_error_mm']/1e3+np.deg2rad(best['rerror_deg'])/30:best=rec
 records.append(best);print(json.dumps(best))
(r/'out/waypoints_trial03.json').write_text(json.dumps(records,indent=2))