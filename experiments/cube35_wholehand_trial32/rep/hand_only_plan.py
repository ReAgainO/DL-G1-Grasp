import json,time
from pathlib import Path
import numpy as np,mujoco
from scipy.optimize import least_squares
import real_hand,sonic_grasp as g
root=Path.cwd();m=mujoco.MjModel.from_xml_path(str(root/'out/pose_plan03/scene.xml'));d=mujoco.MjData(m)
jids=m.actuator_trnid[:,0];qa=m.jnt_qposadr[jids];d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[qa[:29]]=g.neutral_body(m,g.s.DEFAULT_ANGLES,.2);d.qpos[qa[36:43]]=g.core.CLOSED
active=np.array([0,1,2,5,6]);j=jids[36:43][active];lo=m.jnt_range[j,0]+.080;hi=m.jnt_range[j,1]-.080
markers=[m.geom(real_hand.PADS[i]).id for i in [0,2]];bids=[m.body(real_hand.DISTAL[i]).id for i in [0,2]];wrist=m.body('right_wrist_yaw_link').id
rng=np.random.default_rng(42);best=[]
def calc(x):
 d.qpos[qa[36:43][active]]=x;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
 R=d.xmat[wrist].reshape(3,3);p=d.xpos[wrist]
 points=(d.geom_xpos[markers]-p)@R
 normals=np.array([R.T@d.xmat[bids[0]].reshape(3,3)@np.array([tsign,0,0]),R.T@d.xmat[bids[1]].reshape(3,3)@np.array([0,msign,0])])
 return points,normals
for si in range(12):
 tsign=1.;msign=1.
 x0=np.clip(g.core.CLOSED[active],lo,hi) if si%9==0 else rng.uniform(lo,hi)
 def r(x):
  ps,ns=calc(x);return np.r_[150*(ps[1]-ps[0]-.042*ns[0]),3*(ns[0]+ns[1])]
 o=least_squares(r,x0,bounds=(lo,hi),max_nfev=180,ftol=1e-9,xtol=1e-9,gtol=1e-9)
 ps,ns=calc(o.x);q=g.core.CLOSED.copy();q[active]=o.x;q[3:5]=[.1,.1]
 row={'seed':si,'thumb_side':tsign,'middle_side':msign,'cost':float(o.cost),'hand_q':q.tolist(),'points_wrist':ps.tolist(),'normals_wrist':ns.tolist(),'gap_mm':float(np.linalg.norm(ps[1]-ps[0])*1000),'opposition_deg':float(np.rad2deg(np.arccos(np.clip(-ns[0]@ns[1],-1,1))))}
 best.append(row)
print(json.dumps(sorted(best,key=lambda x:x['cost'])[:6],indent=2))
(root/'out/hand_only_candidates.json').write_text(json.dumps(best,indent=2))