from pathlib import Path
import json,numpy as np,mujoco
from scipy.optimize import least_squares
import sonic_grasp as g,real_hand
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial04/scene.xml'));d=mujoco.MjData(m);j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];aq=qa[22:29];lo=m.jnt_range[j[22:29],0]+.04;hi=m.jnt_range[j[22:29],1]-.04
c=min(json.load(open(r/'out/coupled_grasp_candidates05.json')),key=lambda x:x['cost']);assert max(c['point_error_mm'])<15 and not any(abs(x)>.001 for x in c['penalty']);hand=np.array(c['hand_q']);P=np.array(c['wrist_target']);R=np.array(c['wrist_R']);d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[qa[:29]]=g.neutral_body(m,g.s.DEFAULT_ANGLES,0);d.qpos[qa[36:43]]=hand;base=d.qpos.copy();w=m.body('right_wrist_yaw_link').id;markers=[m.geom(n).id for n in real_hand.PADS]
def kin(q):
 d.qpos[:]=base;d.qpos[aq]=q;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
def solve(target,RR,seed):
 def fun(q):
  kin(q);return np.r_[100*(d.xpos[w]-target),g.rot_error(RR,d.xmat[w].reshape(3,3)),.001*(q-seed)]
 o=least_squares(fun,np.clip(seed,lo,hi),bounds=(lo,hi),max_nfev=250);kin(o.x);assert np.linalg.norm(d.xpos[w]-target)<.002;return o.x
q=solve(P,R,np.array(c['decoded_arm']));pre=solve(P+[-.08,0,0],R,q);kin(q);center=(d.geom_xpos[markers[0]]+d.geom_xpos[markers[2]])/2;target=center+[0,0,.1]
def liftfun(qx):
 kin(qx);mid=(d.geom_xpos[markers[0]]+d.geom_xpos[markers[2]])/2;return np.r_[100*(mid-target),.4*g.rot_error(R,d.xmat[w].reshape(3,3)),.025*(qx-q)]
o=least_squares(liftfun,q,bounds=(lo,hi),max_nfev=300);liftfun(o.x);lift_err=float(np.linalg.norm((d.geom_xpos[markers[0]]+d.geom_xpos[markers[2]])/2-target)*1000);assert lift_err<1
old=json.load(open(r/'out/joint_waypoints_trial03.json'))['waypoints'];initial=np.array(old[0]['arm_q']);safe=np.array(old[1]['arm_q']);rec=[]
for n,qq in [('INITIAL',initial),('SAFE',safe),('PRE',pre),('GRASP',q),('LIFT',o.x)]:
 kin(qq);rec.append({'name':n,'arm_q':qq.tolist(),'wrist_p':d.xpos[w].tolist(),'wrist_R':d.xmat[w].reshape(3,3).tolist()})
plan={'roll_deg':60,'score':0.,'arm_q':q.tolist(),'hand_q':hand.tolist(),'wrist_target':P.tolist(),'wrist_R':R.tolist(),'grasp_center':center.tolist(),'origin':'coupled frozen SONIC+hand fit, not prescribed original wrist orientation','frozen_fit':c}
table=m.geom('table_top').id;rest=np.array([0,0,-.6,1,1.5,1,1.5]);coll=[]
for i in range(len(rec)-1):
 for u in np.linspace(0,1,81):
  kin((1-u)*np.array(rec[i]['arm_q'])+u*np.array(rec[i+1]['arm_q']));d.qpos[qa[36:43]]=rest if i<=1 else hand;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);mujoco.mj_collision(m,d)
  for cc in d.contact[:d.ncon]:
   if table in (cc.geom1,cc.geom2) and cc.dist<-.00001:coll.append({'segment':i,'u':float(u),'dist_mm':float(cc.dist*1e3)})
# Also sample unfolding at PRE.
for u in np.linspace(0,1,81):
 kin(pre);d.qpos[qa[36:43]]=(1-u)*rest+u*hand;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);mujoco.mj_collision(m,d)
 for cc in d.contact[:d.ncon]:
  if table in (cc.geom1,cc.geom2) and cc.dist<-.00001:coll.append({'segment':'unfold','u':float(u),'dist_mm':float(cc.dist*1e3)})
print('COLLISIONS',len(coll),'LIFTERRMM',lift_err);print(json.dumps(rec));print(json.dumps(coll[:8]));(r/'out/pose_plan_candidates05.json').write_text(json.dumps([plan],indent=2));(r/'out/joint_waypoints05.json').write_text(json.dumps({'waypoints':rec,'table_penetrations':coll,'lift_position_error_mm':lift_err,'grasp_plan':plan},indent=2))