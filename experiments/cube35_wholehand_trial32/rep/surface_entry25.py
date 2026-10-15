"""Static opening/closing and approach for surface plan; no physics success."""
exec((__import__('pathlib').Path(__file__).parent/'coupled_surface_plan.py').read_text().split('for axis in [1,0]:')[0].replace('surface_plan22','surface_entry25'))
import sonic_grasp as g
p=json.loads((r/'out/surface_path22/paths.json').read_text())[0];plan=p['grasp'];x=np.array(plan['q']);pp0,nn0=pose(x);way=[];qseed=x.copy()
for gap in np.linspace(0,.012,25):
 target=pp0.copy();axis=plan['axis'];sg=plan['thumb_side_sign'];target[0,axis]+=sg*gap;target[1,axis]-=sg*gap
 def fun(xx):
  pp,nn=pose(xx)
  reg=.012*(xx-x);reg[10:12]=.025*(xx[10:12]-[1.3,1.7])
  return np.r_[180*(pp-target).ravel(),.5*(nn-nn0).ravel(),reg,800*collision()]
 opt=least_squares(fun,qseed,bounds=(lo,hi),max_nfev=140,diff_step=1e-5,ftol=1e-8,xtol=1e-8,gtol=1e-8);qseed=opt.x;rr=fun(qseed)
 way.append(dict(gap=float(gap),arm_q=qseed[:7].tolist(),hand_q=qseed[7:].tolist(),point_error_mm=float(np.linalg.norm(rr[:6].reshape(2,3)/180,axis=1).max()*1000),penalty_mm=float(collision().max()*1000),wrist_xyz=d.xpos[w].tolist(),wrist_R=d.xmat[w].reshape(3,3).tolist()))
openx=qseed.copy();openpoints,opennormals=pose(openx);raiseq=openx[:7].copy();above=[]
for h in np.linspace(0,.08,9):
 target=openpoints+[0,0,h]
 def fun(q):
  xx=openx.copy();xx[:7]=q;pp,nn=pose(xx)
  return np.r_[180*(pp-target).ravel(),.5*(nn-opennormals).ravel(),.01*(q-raiseq),800*collision()]
 opt=least_squares(fun,raiseq,bounds=(lo[:7],hi[:7]),max_nfev=100,diff_step=1e-5);raiseq=opt.x;rr=fun(raiseq)
 above.append(dict(height=float(h),arm_q=raiseq.tolist(),hand_q=openx[7:].tolist(),point_error_mm=float(np.linalg.norm(rr[:6].reshape(2,3)/180,axis=1).max()*1000),penalty_mm=float(collision().max()*1000),wrist_xyz=d.xpos[w].tolist(),wrist_R=d.xmat[w].reshape(3,3).tolist()))
initial=base[qa[idx]].copy();rest=initial[7:].copy();collisions=[]
for u in np.linspace(0,1,101):
 xx=initial.copy();xx[:7]=(1-u)*initial[:7]+u*raiseq;pose(xx);pen=collision()
 if pen.max()>.0001:
  pairs=[]
  for cc in d.contact[:d.ncon]:
   if cc.dist<-.0001 and (cc.geom1 in slots or cc.geom2 in slots) and not (cube in [cc.geom1,cc.geom2] and (cc.geom1 in allowed or cc.geom2 in allowed)):pairs.append([m.geom(cc.geom1).name,m.geom(cc.geom2).name,float(cc.dist)])
  collisions.append(dict(u=float(u),max_penalty_mm=float(pen.max()*1000),pairs=pairs))
res=dict(grasp=plan,opening_path=way,vertical_approach=above,initial_arm=initial[:7].tolist(),rest_hand=rest.tolist(),initial_to_above_collisions=collisions,physics_success=False)
(o/'entry.json').write_text(json.dumps(res,indent=2));print(json.dumps(res),flush=True)
