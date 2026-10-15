import json,numpy as np,mujoco
from pathlib import Path
from scipy.optimize import least_squares
import sonic_grasp as g,real_hand
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial02/scene.xml'));d=mujoco.MjData(m);j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];aq=qa[22:29];lo=m.jnt_range[j[22:29],0]+.04;hi=m.jnt_range[j[22:29],1]-.04
p=json.load(open(r/'out/normal_trial02/result.json'))['selected_plan'];wp=json.load(open(r/'out/waypoints_trial03.json'));way={x['name']:x for x in wp};d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[qa[:29]]=g.neutral_body(m,g.s.DEFAULT_ANGLES,0);d.qpos[qa[36:43]]=p['hand_q'];base=d.qpos.copy();w=m.body('right_wrist_yaw_link').id;markers=[m.geom(n).id for n in real_hand.PADS];R=np.array(p['wrist_R']);center=np.array(p['grasp_center'])
def kin(q):
 d.qpos[:]=base;d.qpos[aq]=q;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
def midpoint():return (d.geom_xpos[markers[0]]+d.geom_xpos[markers[2]])/2
q0=np.asarray(p['arm_q']);kin(q0);local=(center-d.xpos[w])@d.xmat[w].reshape(3,3);target=center+[0,0,.1]
def liftfun(q):
 kin(q);return np.r_[100*(midpoint()-target),.4*g.rot_error(R,d.xmat[w].reshape(3,3)),.025*(q-q0)]
o=least_squares(liftfun,np.clip(q0,lo,hi),bounds=(lo,hi),max_nfev=300);liftfun(o.x);print('LIFT',np.linalg.norm(midpoint()-target)*1000,np.rad2deg(np.linalg.norm(g.rot_error(R,d.xmat[w].reshape(3,3)))))
initial=np.array([.445,-.249,.061,.494,.113,-.242,-.028]);safe=np.array(way['raise_free']['q']);pre=np.array(way['pre']['q'])
# Alternate elbow nullspace tends to reduce wrist pitch; prefer the selected static grasp branch.
rec=[]
for n,q in [('INITIAL',initial),('SAFE',safe),('PRE',pre),('GRASP',q0),('LIFT',o.x)]:
 kin(q);rec.append({'name':n,'arm_q':q.tolist(),'wrist_p':d.xpos[w].tolist(),'wrist_R':d.xmat[w].reshape(3,3).tolist(),'center':midpoint().tolist()})
print(json.dumps(rec))
# Sample intended hand-rest -> pre-shape timing and every original robot/table collision.
table=m.geom('table_top').id;cg=m.geom('red_cube_geom').id;rest=np.array([0,0,-.6,1.0,1.5,1.0,1.5]);coll=[]
for i in range(len(rec)-1):
 for u in np.linspace(0,1,81):
  q=(1-u)*np.array(rec[i]['arm_q'])+u*np.array(rec[i+1]['arm_q']);kin(q)
  d.qpos[qa[36:43]]=rest if i<=1 else np.array(p['hand_q']);mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);mujoco.mj_collision(m,d)
  for c in d.contact[:d.ncon]:
   if table in (c.geom1,c.geom2) and c.dist<-.00001:
    k=c.geom2 if c.geom1==table else c.geom1;coll.append({'segment':rec[i]['name']+'_'+rec[i+1]['name'],'u':float(u),'geom':m.geom(k).name,'body':m.body(int(m.geom_bodyid[k])).name,'dist_mm':float(c.dist*1000)})
print('TABLE_COLLISIONS',len(coll));print(json.dumps(coll[:10]));(r/'out/joint_waypoints_trial03.json').write_text(json.dumps({'waypoints':rec,'table_penetrations':coll,'lift_position_error_mm':float(np.linalg.norm(midpoint()-target)*1000)},indent=2))