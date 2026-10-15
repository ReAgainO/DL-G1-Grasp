import json,numpy as np,mujoco,time
from pathlib import Path
from scipy.optimize import least_squares
import sonic_v11 as s,real_hand
from goal_pose_policy import GoalPoseReference
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial04/scene.xml'));d=mujoco.MjData(m);a=np.load(r/'out/normal_trial04/trajectory.npz');d.qpos[:]=a['qpos'][-1];c=s.SonicV11(m);ref=a['body_reference'][-1];future=np.tile(ref,(10,1));v=np.zeros_like(future);rr=np.tile([1.,0,0,0],(10,1))
for _ in range(15):c.step_policy(d,future,v,rr)
p=GoalPoseReference(c);j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];hqa=qa[36:43];idx=np.array([0,1,2,3,5,6]);hidx=np.array([0,1,2,5,6]);lo=np.r_[m.jnt_range[j[22:29],0][idx]+.025,m.jnt_range[j[36:43],0][hidx]+.06];hi=np.r_[m.jnt_range[j[22:29],1][idx]-.025,m.jnt_range[j[36:43],1][hidx]-.06]
plan=json.load(open(r/'out/normal_trial04/result.json'))['selected_plan'];refseed=np.array(plan['arm_q']);hs=np.array(plan['hand_q']);targets=np.array([[.28,-.118+.021,.7825],[.28,-.118-.021,.7825]]);gids=np.array([m.geom(real_hand.PADS[k]).id for k in [0,2]]);bids=[m.geom_bodyid[k] for k in gids];table=m.geom('table_top').id;cg=m.geom('red_cube_geom').id;physical=real_hand.finger_contacts(m)[1];w=m.body('right_wrist_yaw_link').id
normals=np.array([[1.,0,0],[0,1.,0]]);nr=np.array([[0,-1.,0],[0,1.,0]])
def state(x):
 goal=refseed.copy();goal[idx]=x[:6];hand=hs.copy();hand[hidx]=x[6:];p.predict(d,goal);f=p.f;f.qpos[hqa]=hand;mujoco.mj_kinematics(m,f);mujoco.mj_comPos(m,f);return goal,hand
calls=0
def fun(x):
 global calls
 goal,hand=state(x);f=p.f;points=f.geom_xpos[gids];ns=np.array([f.xmat[b].reshape(3,3)@n for b,n in zip(bids,normals)]);pen=np.zeros(9);mujoco.mj_collision(m,f)
 for cc in f.contact[:f.ncon]:
  if table in (cc.geom1,cc.geom2):
   other=cc.geom2 if cc.geom1==table else cc.geom1
   if other in physical:pen[physical.index(other)]=min(pen[physical.index(other)],cc.dist)
   elif m.geom_bodyid[other]==w:pen[-1]=min(pen[-1],cc.dist)
  if cg in (cc.geom1,cc.geom2):
   other=cc.geom2 if cc.geom1==cg else cc.geom1
   if other in physical or m.geom_bodyid[other]==w:pen[-2]=min(pen[-2],cc.dist)
 calls+=1
 return np.r_[100*(points-targets).flatten(),.35*(ns-nr).flatten(),300*pen,.004*(x-np.r_[refseed[idx],hs[hidx]])]
def jac(x):
 y=fun(x);J=np.zeros((len(y),len(x)));eps=.02
 for k in range(len(x)):
  xx=x.copy();dq=eps if x[k]+eps<hi[k] else -eps;xx[k]+=dq;J[:,k]=(fun(xx)-y)/dq
 return J
results=[]
for seed in [refseed,ref[22:29],np.array([-.2,.4,.3,.1,-.5,1.2,-1.0])]:
 tic=time.monotonic();x=np.clip(np.r_[seed[idx],hs[hidx]],lo,hi);o=least_squares(fun,x,jac=jac,bounds=(lo,hi),max_nfev=100,ftol=1e-7,xtol=1e-7,gtol=1e-7);goal,hand=state(o.x);f=p.f;points=f.geom_xpos[gids].copy();ns=np.array([f.xmat[b].reshape(3,3)@n for b,n in zip(bids,normals)]);error=fun(o.x)
 rec={'cost':float(o.cost),'reference_arm':goal.tolist(),'decoded_arm':f.qpos[qa[22:29]].tolist(),'hand_q':hand.tolist(),'wrist_target':f.xpos[w].tolist(),'wrist_R':f.xmat[w].reshape(3,3).tolist(),'points':points.tolist(),'point_error_mm':(np.linalg.norm(points-targets,axis=1)*1e3).tolist(),'normal_error_deg':np.rad2deg(np.arccos(np.clip(np.sum(ns*nr,axis=1),-1,1))).tolist(),'penalty':error[12:21].tolist(),'nfev':o.nfev,'wall_s':time.monotonic()-tic}
 print(json.dumps(rec),flush=True);results.append(rec)
(r/'out/coupled_grasp_candidates05.json').write_text(json.dumps(results,indent=2))