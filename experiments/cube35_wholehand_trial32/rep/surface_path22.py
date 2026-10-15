"""Validate whole-mesh lifted path; static only, no success claim."""
exec((__import__('pathlib').Path(__file__).parent/'coupled_surface_plan.py').read_text().split('for axis in [1,0]:')[0].replace("surface_plan22","surface_path22"))
from scipy.optimize import least_squares
import sonic_grasp as g
records=[]
candidates=json.loads((r/'out/surface_plan22/candidates.json').read_text())
for plan in [candidates[6],candidates[1]]:
 x=np.array(plan['q']);pp,nn=pose(x);arm=x[:7].copy();points0=pp.copy();normal0=nn.copy();R0=d.xmat[w].reshape(3,3).copy();stages=[]
 for h in np.linspace(0,.1,11):
  targets=points0+np.array([0,0,h])
  def fun(q):
   xx=x.copy();xx[:7]=q;pp,nn=pose(xx)
   # Translate object in FK data solely for hypothetical geometric path.
   d.qpos[m.jnt_qposadr[m.body_jntadr[cb]]:][:3]=cp+np.array([0,0,h])
   mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
   return np.r_[200*(pp-targets).ravel(),.8*(nn-normal0).ravel(),.008*(q-arm),600*collision()]
  opt=least_squares(fun,arm,bounds=(lo[:7],hi[:7]),max_nfev=100,diff_step=1e-5,ftol=1e-8,xtol=1e-8,gtol=1e-8);arm=opt.x;rr=fun(arm)
  contact=[]
  for cc in d.contact[:d.ncon]:
   if cube in [cc.geom1,cc.geom2]:
    other=cc.geom2 if cc.geom1==cube else cc.geom1
    contact.append(dict(geom=m.geom(other).name,dist_mm=float(cc.dist*1000),point=cc.pos.tolist(),normal=(cc.frame[:3]*(1 if cc.geom2==cube else -1)).tolist()))
  stages.append(dict(height=h,arm_q=arm.tolist(),point_error_mm=float(np.linalg.norm(rr[:6].reshape(2,3)/200,axis=1).max()*1000),max_penalty_mm=float(collision().max()*1000),orientation_delta_deg=float(np.rad2deg(np.linalg.norm(g.rot_error(R0,d.xmat[w].reshape(3,3))))),wrist_xyz=d.xpos[w].tolist(),wrist_R=d.xmat[w].reshape(3,3).tolist(),contacts=contact))
 # Open thumb and middle by 5mm each using the same material patches.
 x=np.array(plan['q']);axis=plan['axis'];sg=plan['thumb_side_sign'];p0,n0=pose(x);open_targets=p0.copy();open_targets[0,axis]+=sg*.005;open_targets[1,axis]-=sg*.005
 def opening(q):
  xx=x.copy();xx[7:]=q;pp,nn=pose(xx)
  return np.r_[150*(pp-open_targets).ravel(),.2*(nn-n0).ravel(),.002*(q-x[7:]),600*collision()]
 op=least_squares(opening,x[7:],bounds=(lo[7:],hi[7:]),max_nfev=120,ftol=1e-8,xtol=1e-8,gtol=1e-8);oe=opening(op.x)
 rec=dict(grasp=plan,lift_path=stages,open_hand_q=op.x.tolist(),open_point_error_mm=float(np.linalg.norm(oe[:6].reshape(2,3)/150,axis=1).max()*1000),open_penalty_mm=float(collision().max()*1000),geometry_only=True,physics_success=False)
 records.append(rec);(o/'paths.json').write_text(json.dumps(records,indent=2))
 print(json.dumps(rec),flush=True)
