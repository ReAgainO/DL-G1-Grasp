"""Physical-collision G1/Dex3 task. All body targets from SONIC; no object/state overrides."""
import argparse,json,time,gzip,hashlib
from pathlib import Path
import numpy as np,mujoco
import sonic_grasp as g,sonic_v11 as s,source_physics_core as core,real_hand
from reference_filter_v2 import ReferenceFilter
from mesh_hand_v5 import MeshHandV5
from finger_control import finger_torques
from contact_audit import ContactAudit
from balance_audit import BalanceAudit
from execution_monitor import ExecutionMonitor
from motion_input import ArdyMotion
from stable_hand import stable_hand_torques
from mesh_token_policy_v5 import MeshTokenReferenceV5

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def quint(x):x=np.clip(x,0,1);return x*x*x*(10-15*x+6*x*x)
def kin(m,f):mujoco.mj_kinematics(m,f);mujoco.mj_comPos(m,f)
def wrist_ik(m,f,aq,av,w,target,R,prior):
 q=f.qpos[aq].copy();jr=np.zeros((3,m.nv));jp=jr.copy();jids=m.dof_jntid[av];lo=m.jnt_range[jids,0]+.006;hi=m.jnt_range[jids,1]-.006
 for _ in range(22):
  f.qpos[aq]=q;kin(m,f);ep=target-f.xpos[w];er=g.rot_error(R,f.xmat[w].reshape(3,3));mujoco.mj_jacBody(m,f,jp,jr,w)
  J=np.vstack([10*jp[:,av],jr[:,av]]);r=np.r_[10*ep,er];pinv=J.T@np.linalg.solve(J@J.T+1e-5*np.eye(6),np.eye(6))
  dq=pinv@r+.005*(np.eye(7)-pinv@J)@(prior-q);dq*=min(1.,.08/max(abs(dq).max(),1e-12));q=np.clip(q+dq,lo,hi)
  if np.linalg.norm(ep)<.0004 and np.linalg.norm(er)<.005:break
 return q

def run(name,no_grip=False):
 root=Path(__file__).resolve().parent;out=root/'out'/name;out.mkdir();tic=time.monotonic()
 plans=json.loads((root/'out/pose_plan_candidates16.json').read_text());plan=min([p for p in plans if p['roll_deg']==60 and p['score']<.01],key=lambda p:abs(p['arm_q'][-1]))
 assert plan['score']<.01
 pathplan=json.loads((root/'out/joint_waypoints16.json').read_text());assert not pathplan['table_penetrations'];assert pathplan['lift_position_error_mm']<1;assert pathplan['grasp_plan']==plan;way={p['name']:p for p in pathplan['waypoints']}
 scene,*_=g.scene_and_cal(root,out,direct_table=True,table_front=.24,cube_x=.28,cube_y=-.118,cube_edge_mm=50.)
 m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m);assert m.nu==43 and m.nq==57 and m.neq==0
 ctrl=s.SonicV11(m);jids=m.actuator_trnid[:,0];qa=m.jnt_qposadr[jids];va=m.jnt_dofadr[jids]
 aq=qa[22:29];av=va[22:29];hq=qa[36:43];hv=va[36:43];neutral=g.neutral_body(m,s.DEFAULT_ANGLES,0.);neutral[22:29]=way['INITIAL']['arm_q'];neutral[15:22]=np.array(way['INITIAL']['arm_q'])*np.array([1,-1,-1,1,-1,1,-1])
 d.qpos[:3]=[-.06,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[qa[:29]]=neutral
 prehand=np.asarray(plan['hand_q']).copy();prehand[3:5]=[1.3,1.7];resthand=np.array([0.,0.,-.6,1.3,1.7,1.3,1.7]);leftrest=-resthand;d.qpos[qa[29:36]]=leftrest;d.qpos[hq]=resthand;mujoco.mj_forward(m,d);assert m.opt.timestep==.002
 initaction=((d.qpos[ctrl.aq]-s.DEFAULT_ANGLES)/s.ACTION_SCALE)[s.I2M].astype(np.float32);ctrl.last_action=initaction.copy()
 for key,arr in {'gyro':np.zeros(3),'q':d.qpos[ctrl.aq][s.I2M]-s.DEFAULT_ANGLES[s.I2M],'v':np.zeros(29),'action':initaction,'gravity':np.array([0.,0.,-1.])}.items():ctrl.hist[key].clear();ctrl.hist[key].extend([arr.copy() for _ in range(10)])
 finger_groups,contact_geoms=real_hand.finger_contacts(m);cube=m.body('red_cube').id;cg=m.geom('red_cube_geom').id;w=m.body('right_wrist_yaw_link').id;table=m.geom('table_top').id;floor=m.geom('floor').id
 tabletop=float(d.geom_xpos[table,2]+m.geom_size[table,2]);initial_cube=d.xpos[cube].copy();cubehalf=float(m.geom_size[cg,0])
 motion=ArdyMotion(root/'src/original_motions/new_motion_cube_a_s42.npz',check_csv=root/'src/original_motions/new_motion_cube_a_s42.csv')
 stamp={'mujoco':mujoco.__version__,'model_sha':{'scene':sha(scene),'robot':sha(out/'g1_free_grasp.xml')},'source_sha':{k:sha(root/(k+'.py')) for k in ['normal_runner19','mesh_contact_v4','mesh_hand_v5','mesh_token_policy_v5','reference_filter_v2','real_hand','sonic_v11','adaptive_hand','grasp_geometry','reference_filter','finger_control','stable_hand','pose_policy','source_physics_core','sonic_grasp','contact_audit','balance_audit','execution_monitor','motion_input']},'sonic_weights':ctrl.model_stamp,'ardy':motion.audit,'ardy_use':'standalone SONIC+hand calibration; old motion read and IK prior computed but not used by active discrete reference-search branch; fresh ARDY integration pending','gate_definition':'v6 real physical digit surfaces, no sphere contacts','scene_parameters':{'cube_initial_xyz':initial_cube.tolist(),'robot_initial_xyz':[-.06,0,.788740],'cube_edge_m':2*cubehalf,'cube_mass_kg':float(m.body_mass[cube]),'table_top_z_m':tabletop,'cube_friction':m.geom_friction[cg].tolist()},'selected_plan':plan,'plan_file_sha':sha(root/'out/pose_plan_candidates16.json'),'joint_plan_sha':sha(root/'out/joint_waypoints16.json'),'joint_plan':pathplan}
 (out/'runtime.json').write_text(json.dumps(stamp,indent=2))
 contact=ContactAudit(m,cube,cg,contact_geoms,{table,floor},out,stamp);balance=BalanceAudit(m,{table,floor},stamp,out);execution=ExecutionMonitor(m,1.4)
 fk=mujoco.MjData(m);ref=neutral.copy();lo=m.jnt_range[jids[22:29],0]+.006;hi=m.jnt_range[jids[22:29],1]-.006;rf=ReferenceFilter(ref[22:29],lo,hi,True);goal=ref[22:29].copy()
 solver=MeshHandV5(m,opponent=2,preload_m=.0015,face_half_m=.009);solver.lo+=.018;solver.hi-=.018;cmd=resthand.copy();handgoal=cmd.copy();normal=None
 inverse_pose=MeshTokenReferenceV5(ctrl);solver.surfaces=inverse_pose.surfaces;transfer_pass=False;transfer_cube_z=None
 phase='SETTLE';start=0.;events=[{'phase':phase,'time':0.}];wp=d.xpos[w].copy();wR=d.xmat[w].reshape(3,3).copy();origin=wp.copy();originR=wR.copy();Gp=np.asarray(plan['wrist_target']);GR=np.asarray(plan['wrist_R']);capture_wp=None;capture_R=None;capture_rel=None;origin_arm=neutral[22:29].copy();desired=origin_arm.copy();capture_mid=None;target_mid=None;capture_cube=None;capture_cube_R=None;force_anchor_by_group={};grip_anchor_manifest=None;capture_hand=None
 rows=[];frames=[];refs=[];actions=[];hands=[];phases=[];dwell=0.;fail=None;hold_start=hold_end=release_start=None;maxext=0.;prediction_checks=0;prediction_max_error=0.;warnings0=np.array([x.number for x in d.warning]);handlimit=0.;target_wp=wp.copy();target_R=wR.copy();count=0;hand_table_rejections=0;hand_check=mujoco.MjData(m);self_contact_max=0.;self_contact_pair=None;arm_tracking_error=0.
 def change(p):
  nonlocal phase,start,origin,originR,dwell,capture_wp,capture_R,normal,hold_start,hold_end,release_start,transfer_cube_z,capture_rel,origin_arm,capture_mid,capture_cube,capture_cube_R,grip_anchor_manifest,capture_hand
  origin_arm=d.qpos[aq].copy();phase=p;start=d.time;origin=d.xpos[w].copy();originR=d.xmat[w].reshape(3,3).copy();dwell=0.;events.append({'phase':p,'time':float(d.time)})
  if p=='CLOSE':
   normal=d.geom_xpos[m.geom(core.PADS[2]).id]-d.geom_xpos[m.geom(core.PADS[0]).id]
  if p=='TEST_LIFT':
   capture_hand=handgoal.copy();capture_cube=d.xpos[cube].copy();capture_cube_R=d.xmat[cube].reshape(3,3).copy();groups=np.array([0,2]);assert all(int(k) in force_anchor_by_group for k in groups);grip_anchor_manifest=[force_anchor_by_group[int(k)] for k in groups];inverse_pose.grip_anchors=grip_anchor_manifest;inverse_pose.captured_normals=np.array([d.geom_xmat[a['geom']].reshape(3,3)@np.array(a['local_normal']) for a in grip_anchor_manifest])
   ps=np.array([d.geom_xpos[a['geom']]+d.geom_xmat[a['geom']].reshape(3,3)@np.array(a['local_point']) for a in grip_anchor_manifest]);inverse_pose.sep_target=5*(ps[0,[0,2]]-ps[1,[0,2]]);capture_mid=ps.mean(axis=0);capture_wp=origin.copy();capture_R=originR.copy();transfer_cube_z=float(d.xpos[cube,2]);capture_rel=capture_R.T@(d.xpos[cube]-origin)
  if p=='HOLD':hold_start=d.time
  if p=='RELEASE':hold_end=d.time;release_start=d.time
 for step in range(65000):
  e=d.time-start
  if step%10==0:
   if phase=='ALIGN':
    proj=d.xmat[cube].reshape(3,3).T@np.array([0.,-1.,0.]);axis=int(np.argmax(abs(proj[:2])));old=solver.surfaces.axis
    if abs(proj[old])>=abs(proj[axis])-.15:axis=old
    solver.surfaces.axis=axis;solver.surfaces.axis_sign=float(np.sign(proj[axis]))
   shifted=Gp+(d.xpos[cube]-initial_cube) if phase in ['ALIGN','CLOSE'] else Gp.copy()
   if phase in ['SETTLE','RAISE','APPROACH','PRESHAPE','ALIGN']:
    endpoint=neutral[22:29] if phase=='SETTLE' else np.array(way['SAFE' if phase=='RAISE' else 'PRE' if phase in ['APPROACH','PRESHAPE'] else 'GRASP']['arm_q'])
    duration=8 if phase in ['RAISE','APPROACH'] else 6 if phase=='ALIGN' else 0
    desired=endpoint if duration==0 else origin_arm+quint(e/duration)*(endpoint-origin_arm)
    fk.qpos[:]=d.qpos;fk.qpos[aq]=desired;kin(m,fk);target_wp=fk.xpos[w].copy();target_R=fk.xmat[w].reshape(3,3).copy()
    if phase=='ALIGN' and e>=6:target_wp=shifted.copy();target_R=GR.copy()
   elif phase=='CLOSE':target_wp=shifted.copy();target_R=GR.copy()
   else:
    height=.012*quint(e/4) if phase=='TEST_LIFT' else .012+.088*quint(e/12) if phase=='LIFT' else .1
    target_R=g.rotation_blend(capture_R,np.array(way['LIFT']['wrist_R'])@GR.T@capture_R,height/.1)
    target_wp=capture_wp+capture_R@capture_rel+np.array([0,0,height])-target_R@capture_rel
   if step%1000==0:
    if phase=='ALIGN' and e>=6 and e<8:goal=np.array(plan['frozen_fit']['reference_arm'])
    inverse_pose.point_target=None
    if phase in ['ALIGN','CLOSE']:inverse_pose.point_target=d.xpos[cube].copy()+np.array([0,0,.002])
    elif phase in ['TEST_LIFT','LIFT','HOLD','RELEASE','FINAL']:inverse_pose.point_target=capture_mid+np.array([0,0,height])
    target_mid=inverse_pose.point_target
    if phase in ['CLOSE','TEST_LIFT','LIFT','HOLD','RELEASE','FINAL'] or phase=='ALIGN' and e>=6:
     fk.qpos[:]=d.qpos;prior=motion.sample(np.array([min(motion.times[-1],max(0,d.time-2)/12)]))[0][0,22:29]
     desired=wrist_ik(m,fk,aq,av,w,target_wp,target_R,prior)
    if phase in ['SETTLE','RAISE','APPROACH','PRESHAPE']:goal=np.clip(desired,lo,hi)
    else:goal=inverse_pose.update(d,goal,target_wp,target_R,lo,hi)
   future=np.repeat(neutral[None],10,axis=0);fv=np.zeros_like(future)
   qf,vf=rf.step(goal);future[:,22:29]=qf;fv[:,22:29]=vf;ref=future[0].copy();ctrl.step_policy(d,future,fv,np.tile([1.,0,0,0],(10,1)))
  d.ctrl[:29]=ctrl.torques(d,1.,1.,2.)
  if d.time<4.:
   alpha=.1+.9*quint(d.time/4.);tau=s.KP*(ctrl.target-d.qpos[ctrl.aq])-s.KD*d.qvel[ctrl.av];tau[15:29]-=s.KD[15:29]*d.qvel[ctrl.av[15:29]]
   tau[15:29]-=(1-alpha)*s.KP[15:29]*(ctrl.target[15:29]-d.qpos[ctrl.aq[15:29]])
   tau[22:29]+=ctrl.last_gravity_arm
   d.ctrl[:29]=np.clip(tau,m.actuator_ctrlrange[:29,0],m.actuator_ctrlrange[:29,1])
  d.ctrl[15:22]=np.clip(d.ctrl[15:22]+ctrl.gravity_fk.qfrc_bias[ctrl.av[15:22]],m.actuator_ctrlrange[15:22,0],m.actuator_ctrlrange[15:22,1])
  if phase in ['PRESHAPE','ALIGN']:handgoal=prehand.copy()
  if phase in ['ALIGN','CLOSE'] and not no_grip and e>2:
   if step%100==0:
    if normal is None:normal=d.geom_xpos[m.geom(core.PADS[2]).id]-d.geom_xpos[m.geom(core.PADS[0]).id]
    grip_goal=d.xpos[cube].copy() if phase in ['ALIGN','CLOSE'] else capture_cube+np.array([0,0,height]);grip_R=d.xmat[cube].reshape(3,3) if phase in ['ALIGN','CLOSE'] else capture_cube_R
    proposed_hand=solver.solve(d,grip_goal,grip_R,cmd,normal,table_top_z=tabletop,table_clearance_m=.009)
    hand_check.qpos[:]=d.qpos;hand_check.qpos[hq]=proposed_hand;kin(m,hand_check);mujoco.mj_collision(m,hand_check)
    blocked=any(table in [cc.geom1,cc.geom2] and (cc.geom1 in contact_geoms or cc.geom2 in contact_geoms) and cc.dist<0 for cc in hand_check.contact[:hand_check.ncon])
    if blocked:hand_table_rejections+=1
    else:handgoal=proposed_hand
  if phase in ['TEST_LIFT','LIFT','HOLD']:handgoal=capture_hand.copy()
  if phase=='RELEASE':handgoal=prehand.copy()
  if no_grip:handgoal=prehand.copy()
  cmd+=np.clip(handgoal-cmd,-.001,.001)
  kp,kd=core.gains();d.ctrl[36:43]=stable_hand_torques(m,d,hq,hv,cmd,kp[core.HAND],kd[core.HAND],m.actuator_ctrlrange[36:43],3.)
  d.ctrl[29:36]=stable_hand_torques(m,d,qa[29:36],va[29:36],leftrest,kp[core.HAND],kd[core.HAND],m.actuator_ctrlrange[29:36],3.)
  maxext=max(maxext,float(abs(d.xfrc_applied).max()),float(abs(d.qfrc_applied).max()));mujoco.mj_step(m,d);execution.step(d,phase);contact.begin(d,phase,step)
  forces=np.zeros(3);side_forces=np.zeros(3);side_normals=np.zeros((3,3));force_anchor_by_group={};support=0.;arm_tracking_error=max(arm_tracking_error,float(abs(d.qpos[aq]-ctrl.target[22:29]).max()))
  for k,cx in enumerate(d.contact[:d.ncon]):
   if int(m.geom_bodyid[cx.geom1]) in contact.robot_bodies and int(m.geom_bodyid[cx.geom2]) in contact.robot_bodies:
    sf=np.zeros(6);mujoco.mj_contactForce(m,d,k,sf)
    if sf[0]>self_contact_max:self_contact_max=float(sf[0]);self_contact_pair={'time':float(d.time),'phase':phase,'geom1':m.geom(cx.geom1).name,'geom2':m.geom(cx.geom2).name,'body1':m.body(int(m.geom_bodyid[cx.geom1])).name,'body2':m.body(int(m.geom_bodyid[cx.geom2])).name}
  for k,c in enumerate(d.contact[:d.ncon]):
   if cg not in [c.geom1,c.geom2]:continue
   other=c.geom2 if c.geom1==cg else c.geom1;f=np.zeros(6);mujoco.mj_contactForce(m,d,k,f);contact.record(c,k,f)
   if other in finger_groups:
    group=finger_groups[other];forces[group]+=max(0.,f[0]);sign=1 if c.geom2==cg else -1;wn=sign*c.frame[:3];ln=d.xmat[cube].reshape(3,3).T@wn;lp=d.xmat[cube].reshape(3,3).T@(c.pos-d.xpos[cube]);qualified=abs(ln[solver.surfaces.axis])>.8 and abs(ln[2])<.35 and abs(lp[2])<cubehalf-.0035
    if qualified:side_forces[group]+=max(0.,f[0]);side_normals[group]+=max(0.,f[0])*wn
    prev=force_anchor_by_group.get(group)
    if qualified and (prev is None or f[0]>prev['normal_N']):force_anchor_by_group[group]={'geom':int(other),'geom_name':m.geom(other).name,'group':int(group),'local_point':(d.geom_xmat[other].reshape(3,3).T@(c.pos-d.geom_xpos[other])).tolist(),'local_normal':(d.geom_xmat[other].reshape(3,3).T@wn).tolist(),'normal_N':float(f[0]),'time':float(d.time)}
   if other in [table,floor]:support+=max(0.,f[0])
  contact.end();balance.step(d,phase)
  limits=m.jnt_range[jids[36:43]];handlimit=max(handlimit,float(np.maximum(limits[:,0]-d.qpos[hq],d.qpos[hq]-limits[:,1]).max()))
  wr=d.xmat[w].reshape(3,3);rel=wr.T@(d.xpos[cube]-d.xpos[w]);bottom=d.xpos[cube,2]-cubehalf*abs(d.xmat[cube].reshape(3,3)[2]).sum();err=float(np.linalg.norm(target_wp-d.xpos[w]));rerr=float(np.linalg.norm(g.rot_error(target_R,wr)))
  rows.append([d.time,*d.xpos[cube],*rel,*forces,support,bottom,float(s.rotation(d.qpos[3:7])[2,2]),err,rerr,*d.qpos[hq],*cmd,*d.ctrl[36:43]])
  if step%20==0:frames.append(d.qpos.copy());refs.append(ref.copy());actions.append(ctrl.target.copy());hands.append(cmd.copy());phases.append(phase)
  if step%500==0:print(json.dumps({'time':round(float(d.time),2),'phase':phase,'wrist_error_mm':round(err*1000,2),'orientation_deg':round(np.rad2deg(rerr),2),'cube_lift_mm':round((d.xpos[cube,2]-initial_cube[2])*1000,2),'forces':forces.tolist()}),flush=True)
  if not np.isfinite(d.qpos).all() or d.qpos[2]<.55 or s.rotation(d.qpos[3:7])[2,2]<.85:fail='fall_or_nonfinite';break
  ready=err<.025 and abs(d.qvel[av]).max()<.3
  if phase in ['ALIGN','CLOSE']:
   pts=solver.surfaces.points(d,d.xpos[cube],d.xmat[cube].reshape(3,3),cubehalf,.002);mid=pts.mean(axis=0);ready=np.linalg.norm(mid-d.xpos[cube]-np.array([0,0,.002]))<.008 and abs(pts[0,[0,2]]-pts[1,[0,2]]).max()<.007 and abs(d.qvel[av]).max()<.3
  if phase=='SETTLE' and e>=4:change('RAISE')
  elif phase in ['RAISE','APPROACH']:
   if e>=12 and (err<.05 and abs(d.qvel[av]).max()<.3):change('APPROACH' if phase=='RAISE' else 'PRESHAPE')
   elif e>36:fail=phase.lower()+'_pose_timeout';break
  elif phase=='PRESHAPE':
   if e>=3 and abs(d.qpos[hq]-prehand).max()<.08:change('ALIGN')
   elif e>8:fail='preshape_timeout';break
  elif phase=='ALIGN':
   precontact=(forces>.05).sum()>=2 and contact.totals[1:3,0].sum()<.001
   dwell=dwell+.002 if precontact else 0.
   if e>=6 and (ready or dwell>=.1):change('CLOSE')
   elif e>45:fail='alignment_pose_timeout';break
  elif phase=='CLOSE':
   nn0=side_normals[0]/max(np.linalg.norm(side_normals[0]),1e-12);nn2=side_normals[2]/max(np.linalg.norm(side_normals[2]),1e-12);opposed=side_forces[0]>.1 and side_forces[2]>.1 and nn0@nn2<-.5
   dwell=dwell+.002 if opposed else 0.
   if no_grip and e>2:change('TEST_LIFT')
   elif e>1 and dwell>=.2:change('TEST_LIFT')
   elif e>20:fail='true_finger_contact_timeout';break
  elif phase=='TEST_LIFT':
   good=(forces>.1).sum()>=2 and support<.001 and contact.totals[1:3,0].sum()<.001 and d.xpos[cube,2]-transfer_cube_z>.006
   dwell=dwell+.002 if good else 0.
   if e>=4 and (dwell>=.1 or no_grip):transfer_pass=bool(dwell>=.1);change('LIFT')
   elif e>14:fail='test_lift_load_transfer_failure';break
  elif phase=='LIFT':
   if e>=12 and d.xpos[cube,2]-initial_cube[2]>.08 and (forces>.01).sum()>=2 and support<.001:change('HOLD')
   elif e>26:fail='lift_height_or_support_timeout';break
  elif phase=='HOLD' and e>=2:change('RELEASE')
  elif phase=='RELEASE' and e>=1:change('FINAL')
  elif phase=='FINAL' and e>=3:break
 else:fail='total_budget_timeout'
 assert all(sha(root/(k+'.py'))==v for k,v in stamp['source_sha'].items()),'source drift'
 ca=contact.finish(hold_start,hold_end);ba=balance.finish(hold_start,hold_end);ea=execution.finish();a=np.asarray(rows);hm=(a[:,0]>(hold_start or 1e9)+.02)&(a[:,0]<=(hold_end or -1));h=a[hm];after=a[a[:,0]>(release_start or 1e9)+2]
 lift=a[:,3]-initial_cube[2];slip=float(np.linalg.norm(h[:,4:7]-h[0,4:7],axis=1).max()) if len(h) else 1e9;warnings=(np.array([x.number for x in d.warning])-warnings0).tolist()
 gates={'opposed_true_side_grip_before_lift':grip_anchor_manifest is not None,'test_lift_load_transfer':transfer_pass,'completed':fail is None and phase=='FINAL','hold_7cm':len(h)>0 and lift[hm].min()>=.07,'two_real_fingers':len(h)>0 and (h[:,7:10]>.01).sum(axis=1).min()>=2,'no_support':len(h)>0 and h[:,10].max()<.001,'clearance_4cm':len(h)>0 and h[:,11].min()-tabletop>=.04,'slip_1cm':slip<.01,'release_drop_6cm':len(h)>0 and len(after)>0 and h[-1,3]-after[:,3].min()>=.06,'final_supported':a[-1,10]>.05,'final_fingers_off':(a[-1,7:10]>.01).sum()==0,'no_external':maxext==0,'no_warnings':not any(warnings),'upright':a[:,12].min()>.9,'allowed_finger_contacts_in_hold':ca['fingertip_only_robot_contacts_in_hold'],'actual_hand_limits_5mrad':handlimit<=.005,'actual_arm_speed_within_limit':ea['actual_arm_speed_within_limit'],'actual_body_limits_within_2mrad':ea['actual_body_limits_within_2mrad'],'no_robot_table_contact_full_task':ba['robot_table_all_max_normal_N']<.001,**{k:ba[k] for k in ['no_table_rest_in_hold','no_nonfoot_floor_support_in_hold','feet_supported_in_hold']}}
 (out/'execution-audit.json').write_text(json.dumps(ea,indent=2))
 result={'success':all(bool(v) for v in gates.values()),'gates':{k:bool(v) for k,v in gates.items()},'fail_reason':fail,'events':events,'runtime':stamp,'no_grip':no_grip,'selected_plan':plan,'pose_reference_inverse':inverse_pose.audit(),'exact_next_prediction_checks':None,'grasp_face_axis_cube_local':solver.surfaces.axis,'grasp_axis_sign':solver.surfaces.axis_sign,'grip_anchor_manifest':grip_anchor_manifest,'bootstrap_pd_ramp_s':4.,'history_initialization':'repeat actual initial observation; action memory derived from initially held pose, no actual body command before first NN output','left_arm_model_gravity_ff':True,'hand_controller':'implicit mass-matrix PD','execution_audit':ea,'grip_geometry':'closest convex surfaces of original compiled thumb/middle collision meshes, not FK markers','park_left_arm':True,'unused_index_tucked':True,'hand_ik':solver.audit(),'hand_table_target_rejections':hand_table_rejections,'max_self_contact_normal_N':self_contact_max,'peak_self_contact':self_contact_pair,'max_actual_arm_target_gap_rad':arm_tracking_error,'body_target_override':False,'object_state_writes':False,'fixture':False,'contact_model':'actual seven finger link collision geoms; markers collision0; no active fingertip spheres','force_groups':{m.geom(k).name:v for k,v in finger_groups.items()},'sonic':ctrl.audit(),'max_lift_m':float(lift.max()),'hold_min_lift_m':float(lift[hm].min()) if len(h) else None,'hold_slip_m':slip,'max_hand_limit_overshoot_rad':handlimit,'contact_audit_summary':{k:ca[k] for k in ['all_steps','hold_steps','hold_sample_count','fingertip_only_robot_contacts_in_hold']},'balance':ba,'filter':rf.audit(),'simulation_steps':len(rows),'wall_s':time.monotonic()-tic}
 (out/'result.json').write_text(json.dumps(result,indent=2));np.savez_compressed(out/'trajectory.npz',qpos=frames,body_reference=refs,decoded_targets=actions,hand_reference=hands,phase=phases,fps=25,scene=str(scene))
 with gzip.open(out/'telemetry.csv.gz','wt') as f:f.write('time,cube_x,cube_y,cube_z,rel_x,rel_y,rel_z,thumb_N,index_N,middle_N,support_N,bottom_z,upright,wrist_error,rotation_error,'+','.join('actual_hand_q'+str(i) for i in range(7))+','+','.join('hand_target'+str(i) for i in range(7))+','+','.join('hand_tau'+str(i) for i in range(7))+'\n');np.savetxt(f,a,delimiter=',')
 print('RESULT',json.dumps({k:result[k] for k in ['success','fail_reason','gates','max_lift_m','hold_min_lift_m','hold_slip_m','wall_s']}),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('name');ap.add_argument('--no-grip',action='store_true');args=ap.parse_args();run(args.name,args.no_grip)
