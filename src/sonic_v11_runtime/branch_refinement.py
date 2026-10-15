"""Bounded finger-aware redundancy search on static SONIC INPUT arm poses.

Never mj_step, modify actual d or alter motor/object states. Existing candidate
filters remain authoritative. Feasibility is not a dynamic certificate.
"""
import numpy as np,mujoco
import source_physics_core as core
from adaptive_hand import AdaptiveHand
from grasp_geometry import contact_frame

def refine(m,d,aq,av,hq,recipe,target,R,seed,common,opponent,ik,validate,
           preload=.0015,face_half=.015,rounds=3):
 if rounds not in [1,2,3]:raise ValueError('Refinement rounds1..3')
 before=d.qpos.copy();before_v=d.qvel.copy()
 seed=np.asarray(seed,dtype=float);common=np.asarray(common,dtype=float);target=np.asarray(target,dtype=float)
 if seed.shape!=(7,) or common.shape!=(7,) or target.shape!=(3,) or not np.isfinite(np.r_[seed,common,target]).all():raise ValueError('Finite seven-joint source pose/target required')
 limits=m.jnt_range[m.dof_jntid[av]];lo=limits[:,0]+.02001;hi=limits[:,1]-.02001
 table=m.geom('table_top').id;bodies={m.body('pelvis').id}
 for body in range(1,m.nbody):
  if int(m.body_parentid[body]) in bodies:bodies.add(body)
 geoms=[g for g in range(m.ngeom) if int(m.geom_bodyid[g]) in bodies and ((int(m.geom_contype[g])&int(m.geom_conaffinity[table])) or (int(m.geom_contype[table])&int(m.geom_conaffinity[g])))]
 if not 1<=len(geoms)<=128:raise ValueError('Robot geometry count1..128')
 pads=[m.geom(n).id for n in core.PADS];evaluations=0
 def evaluate(q):
  nonlocal evaluations
  evaluations+=1
  if evaluations>1+rounds*17:raise ValueError('Static hand evaluation bound exceeded')
  f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[hq]=recipe;f.qpos[aq]=q;mujoco.mj_forward(m,f)
  capture=float(np.linalg.norm(contact_frame(m,f,R,opponent=opponent)-target));spread=float(np.ptp(f.geom_xpos[pads,2]))
  hs=AdaptiveHand(m,opponent,preload,face_half)
  hs.solve(f,target,R,recipe,f.geom_xpos[pads[opponent]]-f.geom_xpos[pads[0]])
  residual=np.asarray(hs.last['target_points_m'])-np.asarray(hs.last['achievable_points_m'])
  cost=float(np.sum(residual**2))
  f.qpos[hq]=core.OPEN;mujoco.mj_forward(m,f)
  row=dict(body_q=np.asarray(q).tolist(),capture_error_m=capture,pad_spread_m=spread,
   minimum_arm_limit_margin_rad=float(np.min(np.minimum(q-limits[:,0],limits[:,1]-q))),
   open_robot_table_clearance_m=min(float(mujoco.mj_geomDistance(m,f,g,table,.2,None)) for g in geoms),
   finger_replan_error_m=hs.last['max_pad_target_error_m'],native_pose_deviation_rad=float(np.linalg.norm(q-common)))
  try:validate([row])
  except ValueError:pass
  row['hand_plan']=hs.last;row['finger_residual_squared_m2']=cost
  return row
 q=np.clip(seed,lo,hi);best=evaluate(q);trace=[dict(round=0,**best)]
 for rnd in range(rounds):
  if best.get('static_feasible'):break
  f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[hq]=recipe;f.qpos[aq]=q;mujoco.mj_forward(m,f)
  J=contact_frame(m,f,R,av,opponent)[1]
  jac=[]
  for gid in pads:
   jp=np.zeros((3,m.nv));mujoco.mj_jacGeom(m,f,jp,None,gid);jac.append(jp)
  J=np.vstack([J,jac[0][2,av]-jac[1][2,av],jac[2][2,av]-jac[1][2,av]])
  _,values,Vt=np.linalg.svd(J,full_matrices=True);rank=int(np.sum(values>1e-7))
  N=Vt[rank:].T@Vt[rank:]
  gradient=np.zeros(7);eps=.015
  for k in range(7):
   qa=q.copy();qb=q.copy();qa[k]=min(hi[k],q[k]+eps);qb[k]=max(lo[k],q[k]-eps)
   gradient[k]=(evaluate(qa)['finger_residual_squared_m2']-evaluate(qb)['finger_residual_squared_m2'])/max(qa[k]-qb[k],1e-12)
  direction=-N@gradient
  direction/=max(np.max(abs(direction)),1e-12)
  choices=[]
  for step in [.03,.08,.12]:
   guess=np.clip(q+step*direction,lo,hi);f.qpos[hq]=recipe
   trial=ik(m,f,aq,av,target,np.eye(3),guess,common,0.,True,True,True,R,opponent)
   row=evaluate(trial)
   # Never improve finger fit at the cost of the other static filters.
   okay=row['capture_error_m']<=.001 and row['pad_spread_m']<=.002 and row['minimum_arm_limit_margin_rad']>=.02 and row['open_robot_table_clearance_m']>=.01
   if okay:choices.append(row)
  if not choices:break
  selected=min(choices,key=lambda r:r['finger_residual_squared_m2'])
  trace.append(dict(round=rnd+1,**selected,projected_gradient_norm=float(np.linalg.norm(N@gradient)),constraint_rank=rank))
  if selected['finger_residual_squared_m2']>=best['finger_residual_squared_m2']-1e-12:break
  best=selected;q=np.asarray(best['body_q']).copy()
 assert np.array_equal(d.qpos,before) and np.array_equal(d.qvel,before_v)
 return best,dict(round_bound=rounds,evaluation_bound=1+rounds*17,evaluations=evaluations,
  trace=trace,preload_m=preload,face_half_m=face_half,physical_steps=0,actual_state_unchanged=True,
  body_motor_override=False,object_state_writes=False,dynamic_collision_free_certified=False)
