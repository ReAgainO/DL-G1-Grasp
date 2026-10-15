"""Free-base SONIC grasp diagnostic: ARDY prior + explicit calibrated task geometry.

This is a hybrid retargeting method, NOT a native ARDY grasp claim. All 29 body
torques come from official SONIC, with no arm target/torque override. The IK and
bounded integral correction modify only the motion reference entering SONIC.
"""
import argparse,gzip,json,time,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np,mujoco
import source_physics_core as core
import sonic_v11 as s
from motion_input import ArdyMotion
from task_plan import rot_error,rotation_blend
from reference_filter import ReferenceFilter
from policy_reference import PolicyReference
from grasp_geometry import contact_frame

def scene_and_cal(root,out,fixed_base=False):
 assets=root/'src/g1'
 # Rebuild calibration frame solely to recover human-specified wrist geometry.
 caldir=out/'calibration_geometry';caldir.mkdir()
 cm=mujoco.MjModel.from_xml_path(str(core.prepare_model(assets,caldir,[.267,-.118],.7745,True)))
 cd=mujoco.MjData(cm);cal=np.load(root/'src/manual_grasp_calibration.npz',allow_pickle=False)
 low=int(np.argmin(abs(cal['time']-12)));high=int(np.argmin(abs(cal['time']-17.5)))
 cd.qpos[:]=cal['qpos'][low];mujoco.mj_forward(cm,cd)
 wrist=cm.body('right_wrist_yaw_link').id;cube=cm.body('red_cube').id
 offset=(cd.xpos[wrist]-cd.xpos[cube]).copy();lowR=cd.xmat[wrist].reshape(3,3).copy()
 cd.qpos[:]=cal['qpos'][high];mujoco.mj_forward(cm,cd)
 highpos=cd.xpos[wrist].copy();highR=cd.xmat[wrist].reshape(3,3).copy()
 # Preserve floating base and all waist/body actuators. Only finger pad masks
 # match the previously isolated hand experiment; no equality constraints.
 robot=ET.parse(assets/'g1_29dof_with_hand.xml');robot.find('compiler').set('meshdir',str(assets/'meshes'))
 if fixed_base:
  pelvis=robot.find(".//body[@name='pelvis']");assert pelvis is not None and (pelvis.find('freejoint') is not None or pelvis.find("joint[@type='free']") is not None)
  pelvis.set('pos','0 0 .788740')
 for body in robot.iter('body'):
  if body.get('name','').startswith('right_hand_'):
   for geom in body.findall('geom'):
    geom.set('contype','2' if geom.get('name') in core.PADS else '0');geom.set('conaffinity','0')
 robot.write(out/'g1_free_grasp.xml',encoding='utf-8')
 scene=ET.parse(assets/'scene_grasp_hand.xml');scene.find('include').set('file','g1_free_grasp.xml')
 for geom in scene.findall('.//worldbody//geom'):geom.set('conaffinity','3')
 scene.find(".//geom[@name='red_cube_geom']").set('contype','1')
 if fixed_base:
  equality=scene.find('equality')
  if equality is None:equality=ET.SubElement(scene.getroot(),'equality')
  ET.SubElement(equality,'weld',name='robot_base_fixture',body1='pelvis',solref='.002 1')
 scene.write(out/'scene.xml',encoding='utf-8')
 return out/'scene.xml',offset,lowR,highpos,highR

def pinch_center(m,fk,surface=False,cube_R=None):
 if surface:return contact_frame(m,fk,cube_R)
 return (fk.geom_xpos[m.geom(core.PADS[0]).id]+fk.geom_xpos[m.geom(core.PADS[1]).id])*.5

def ik(m,fk,aq,av,target,R,seed,prior,weight,pinch=False,flat_pinch=False,surface=False,cube_R=None):
 q=seed.copy();jid=m.dof_jntid[av];lo=m.jnt_range[jid,0]+.002;hi=m.jnt_range[jid,1]-.002
 wrist=m.body('right_wrist_yaw_link').id;jp=np.zeros((3,m.nv));jr=jp.copy()
 for _ in range(15):
  fk.qpos[aq]=q;mujoco.mj_forward(m,fk)
  if pinch:
   ep=target-pinch_center(m,fk,surface,cube_R);er=np.zeros(3);jp2=jp.copy()
   mujoco.mj_jacGeom(m,fk,jp,jr,m.geom(core.PADS[0]).id);mujoco.mj_jacGeom(m,fk,jp2,None,m.geom(core.PADS[1]).id)
   J=10*(jp[:,av]+jp2[:,av])*.5;err=10*ep
   if surface:J=10*contact_frame(m,fk,cube_R,av)[1]
   if flat_pinch:
    jp3=np.zeros_like(jp);mujoco.mj_jacGeom(m,fk,jp3,None,m.geom(core.PADS[2]).id)
    heights=np.array([fk.geom_xpos[m.geom(core.PADS[0]).id,2]-fk.geom_xpos[m.geom(core.PADS[1]).id,2],
                      fk.geom_xpos[m.geom(core.PADS[2]).id,2]-fk.geom_xpos[m.geom(core.PADS[1]).id,2]])
    J=np.vstack([J,10*(jp[2,av]-jp2[2,av]),10*(jp3[2,av]-jp2[2,av])]);err=np.r_[err,-10*heights];er=heights
  else:
   ep=target-fk.xpos[wrist];er=rot_error(R,fk.xmat[wrist].reshape(3,3))
   mujoco.mj_jacBody(m,fk,jp,jr,wrist);J=np.vstack([10*jp[:,av],jr[:,av]]);err=np.r_[10*ep,er]
  pinv=J.T@np.linalg.solve(J@J.T+1e-4*np.eye(len(J)),np.eye(len(J)))
  dq=pinv@err+weight*(np.eye(7)-pinv@J)@(prior-q)
  dq*=min(1,.08/max(abs(dq).max(),1e-12));q=np.clip(q+dq,lo,hi)
  if np.linalg.norm(ep)<.0003 and np.linalg.norm(er)<.002:break
 return q

def run(name,weight=.03,no_grip=False,pad_off=False,compensation=True,teleop=False,native_geometry=False,pinch_geometry=False,cart_compensation=False,phase_clips=False,capture_radius=.007,flat_pinch=False,c2_reference=False,policy_aware=False,endpoint_seed=False,arm_gain=1.,fixed_base=False,inverse_anchor=False,endpoint_seed_native=False,inverse_incremental=False,kinematic_servo=False,contact_close=False,align_seconds=8.,surface_capture=False,contact_entry_dwell=.2,freeze_close=False):
 start=time.monotonic();root=Path(__file__).resolve().parent;out=root/'out'/name;out.mkdir()
 scene,offset,lowR,highpos,highR=scene_and_cal(root,out,fixed_base)
 m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m)
 assert m.nu==43 and m.nq==57 and m.neq==int(fixed_base) and (m.jnt_type==mujoco.mjtJoint.mjJNT_FREE).sum()==2
 if fixed_base:assert m.eq_obj1id[0]==m.body('pelvis').id and m.eq_obj2id[0]==0
 controller=s.SonicV11(m);load_s=time.monotonic()-start
 motion=ArdyMotion(root/'src/original_motions/near_s42.npz',check_csv=root/'src/original_motions/near_s42.csv')
 phase_motions={};phase_consumed=set();lift_progress=None
 if phase_clips:
  assert pinch_geometry
  for stem in ['lift_s42','hold_s42','release_s42']:
   p=root/'out/generated_phases2'/stem;phase_motions[stem]=ArdyMotion(p.with_suffix('.npz'),check_csv=p.with_suffix('.csv'))
 assert motion.joint_names==[m.joint(int(j)).name for j in controller.jids]
 arm=slice(22,29);aq=controller.aq[arm];av=controller.av[arm]
 hands=np.arange(36,43);hj=m.actuator_trnid[hands,0];hq=m.jnt_qposadr[hj];hv=m.jnt_dofadr[hj]
 d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[controller.aq]=s.DEFAULT_ANGLES;d.qpos[hq]=core.OPEN;mujoco.mj_forward(m,d)
 pads=[m.geom(n).id for n in core.PADS];cg=m.geom('red_cube_geom').id
 if pad_off:
  for g in pads:m.geom_contype[g]=0;m.geom_conaffinity[g]=0
 cube=m.body('red_cube').id;wrist=m.body('right_wrist_yaw_link').id
 def point(data):return pinch_center(m,data,surface_capture,d.xmat[cube].reshape(3,3))
 if surface_capture:assert kinematic_servo and flat_pinch
 supportids={m.geom(n).id for n in ['table_top','cube_pedestal_geom','floor']}
 initial_cube=d.xpos[cube].copy();grasp=initial_cube+offset;initial_base=d.qpos[:3].copy()
 fk=mujoco.MjData(m);geo=mujoco.MjData(m);geo.qpos[:]=d.qpos
 native_curve=[];native_R=[]
 for i in range(len(motion.qpos)):
  geo.qpos[:]=d.qpos;geo.qpos[:3]=[0,0,.74];geo.qpos[3:7]=[1,0,0,0];geo.qpos[controller.aq]=motion.qpos[i,7:]
  mujoco.mj_forward(m,geo);native_curve.append(geo.xpos[wrist].copy());native_R.append(geo.xmat[wrist].reshape(3,3).copy())
 native_curve=np.asarray(native_curve);native_R=np.asarray(native_R)
 if phase_clips:
  lift_z=[]
  for q in phase_motions['lift_s42'].qpos:
   geo.qpos[:]=d.qpos;geo.qpos[:36]=q;mujoco.mj_forward(m,geo);lift_z.append(geo.xpos[wrist,2])
  lift_z=np.maximum.accumulate(lift_z)
  if lift_z[-1]-lift_z[0]<.01:raise RuntimeError('Generated lift has <1cm monotone vertical excursion; reject semantic failure')
  lift_progress=(lift_z-lift_z[0])/(lift_z[-1]-lift_z[0])
 native_frame=int(np.argmax(native_curve[:,0]))
 if native_geometry:
  # Keep the generated near-reach wrist orientation rather than human large
  # wrist rotations. Human calibration contributes ONLY local pinch offset.
  local_offset=lowR.T@offset;lowR=native_R[native_frame].copy();highR=lowR.copy()
  grasp=initial_cube+lowR@local_offset;highpos=grasp+np.array([0,0,.10])
 close_hand=core.CLOSED.copy()
 if pinch_geometry:
  assert not teleop
  close_hand[2]=-.88;grasp=initial_cube.copy();highpos=grasp+np.array([0,0,.10])
  geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo)
  # These are physical pad-frame coordinates, no human calibration endpoints.
  lowR=d.xmat[wrist].reshape(3,3).copy();highR=lowR.copy()
 def native_residual(u):
  x=np.clip(u,0,1)*(len(native_curve)-1);i=int(x);j=min(i+1,len(native_curve)-1);f=x-i
  residual=(1-f)*native_curve[i]+f*native_curve[j]-((1-u)*native_curve[0]+u*native_curve[-1])
  return residual*min(.2,.025/max(np.linalg.norm(residual),1e-12))
 # Human-calibrated route, with an explicit native ARDY redundancy prior.
 phase='SETTLE';phase_start=0.;events=[dict(phase=phase,time_s=0.)];fail=None
 route_start_pos=d.xpos[wrist].copy();route_start_R=d.xmat[wrist].reshape(3,3).copy()
 reference=s.DEFAULT_ANGLES.copy();last_goal=reference[arm].copy();bias=np.zeros(7);cart_bias=np.zeros(3);prev_ref=last_goal.copy();last_v=np.zeros(7)
 lo=m.jnt_range[controller.jids[22:29],0]+.002;hi=m.jnt_range[controller.jids[22:29],1]-.002
 smooth_reference=ReferenceFilter(reference[arm],lo,hi);correction_clipped_cells=0
 inverse_policy=PolicyReference(controller)
 servo_updates=0;servo_max_delta=0.
 if policy_aware:assert c2_reference and pinch_geometry and not teleop and not cart_compensation
 if kinematic_servo:assert c2_reference and pinch_geometry and not policy_aware and not teleop and not cart_compensation
 endpoint=None
 if endpoint_seed:
  assert (policy_aware or kinematic_servo) and flat_pinch
  branch_data=json.loads((root/'out/pinch-feasibility.json').read_text())
  endpoint=branch_data['best']['pregrasp']
  if endpoint_seed_native:
   endpoint=min([r for r in branch_data['records'] if r['target']=='pregrasp' and r['feasible']],key=lambda r:r['native_seed_deviation_rad'])
  assert endpoint['feasible'];endpoint=np.asarray(endpoint['q'])
 alignment_dwell=0.;single_contact_dwell=0.;contact_dwell=0.;hold_start=hold_end=release_start=None;close_reference=None
 rows=[];frames=[];vels=[];references=[];motor_targets=[];raw_motor_targets=[];motor_errors=[];phases=[];calls_ms=[];ik_errors=[];warnings0=np.array([x.number for x in d.warning]);ext=0.
 ardy_prior_effect=[];targetpos=route_start_pos.copy();targetR=route_start_R.copy()
 def change(p,t):
  nonlocal phase,phase_start,route_start_pos,route_start_R,close_reference
  phase=p;phase_start=t;events.append(dict(phase=p,time_s=float(t)))
  route_start_pos=d.xpos[wrist].copy();route_start_R=d.xmat[wrist].reshape(3,3).copy()
  if pinch_geometry:
   geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo);route_start_pos=point(geo).copy()
  if p=='CLOSE':close_reference=reference[arm].copy()
 def quint(x):
  x=np.clip(x,0,1);return x*x*x*(10-15*x+6*x*x)
 for step in range(45000):
  t=step*.002;e=t-phase_start
  if step%10==0:
   if phase=='SETTLE':
    targetpos=d.xpos[wrist].copy();targetR=d.xmat[wrist].reshape(3,3).copy()
    if pinch_geometry:
     geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo);targetpos=point(geo).copy()
   elif phase=='APPROACH':
    # Nominal joint interpolation is converted to Cartesian path before IK.
    u=quint(e/10);geo.qpos[:]=d.qpos;geo.qpos[:3]=[0,0,.74];geo.qpos[3:7]=[1,0,0,0];geo.qpos[controller.aq]=s.DEFAULT_ANGLES
    geo.qpos[aq]=(1-u)*s.DEFAULT_ANGLES[arm]+u*core.SAFE;mujoco.mj_forward(m,geo)
    endpos=geo.xpos[wrist].copy();endR=geo.xmat[wrist].reshape(3,3).copy()
    targetpos=(1-u)*route_start_pos+u*endpos;targetR=rotation_blend(route_start_R,endR,u)
    if native_geometry or pinch_geometry:
     targetpos=(1-u)*route_start_pos+u*highpos+native_residual(u);targetR=rotation_blend(route_start_R,highR,u)
   elif phase=='PREGRASP':
    u=quint(e/12);targetpos=(1-u)*route_start_pos+u*highpos;targetR=rotation_blend(route_start_R,highR,u)
    if native_geometry or pinch_geometry:targetpos+=native_residual(u)
   elif phase in ['DESCEND','ALIGN','CLOSE']:
    u=quint(e/8) if phase=='DESCEND' else 1.;targetpos=(1-u)*highpos+u*grasp;targetR=rotation_blend(highR,lowR,u)
   elif phase=='LIFT':
    u=quint(e/8)
    if phase_clips:u=float(np.interp(np.clip(e/8,0,1),np.linspace(0,1,len(lift_progress)),lift_progress))
    targetpos=(1-u)*grasp+u*highpos;targetR=rotation_blend(lowR,highR,u)
   else:targetpos=highpos.copy();targetR=highR.copy()
   if pinch_geometry and phase in ['DESCEND','ALIGN','CLOSE']:
    grasp=d.xpos[cube].copy() # simulator-state coordinate input, explicitly not vision
    if phase in ['ALIGN','CLOSE']:targetpos=grasp.copy()
    else:
     u=quint(e/8);targetpos=(1-u)*highpos+u*grasp
   prior=motion.sample(np.array([min(motion.times[-1],max(0,t-2)/10)]))[0][0,22:29]
   if phase_clips:
    stem='lift_s42' if phase=='LIFT' else 'hold_s42' if phase=='HOLD' else 'release_s42' if phase in ['RELEASE','SETTLE_RELEASE'] else None
    if stem:
     clip=phase_motions[stem];prior=clip.sample(np.array([min(clip.times[-1],e*.5)]))[0][0,22:29];phase_consumed.add(stem)
   if cart_compensation and pinch_geometry:
    if phase in ['ALIGN','CLOSE']:targetpos=d.xpos[cube].copy()
    if phase in ['ALIGN','CLOSE','LIFT','HOLD']:
     geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo)
     delta=.02*.8*(targetpos-point(geo));cart_bias+=np.clip(delta,-.0005,.0005)
     cart_bias*=min(1,.06/max(np.linalg.norm(cart_bias),1e-12))
   fk.qpos[:]=d.qpos
   if pinch_geometry:fk.qpos[hq]=close_hand
   goal=(last_goal.copy() if policy_aware or kinematic_servo else ik(m,fk,aq,av,targetpos+cart_bias,targetR,last_goal,prior,weight,pinch_geometry,flat_pinch)) if phase!='SETTLE' else s.DEFAULT_ANGLES[arm].copy()
   if endpoint_seed and phase=='APPROACH':goal=endpoint.copy()
   if freeze_close and phase=='CLOSE':goal=close_reference.copy()
   last_goal=goal.copy()
   fk.qpos[aq]=goal;mujoco.mj_forward(m,fk);ik_errors.append([np.linalg.norm(targetpos-(point(fk) if pinch_geometry else fk.xpos[wrist])),np.linalg.norm(rot_error(targetR,fk.xmat[wrist].reshape(3,3)))])
   if compensation and phase!='SETTLE' and not policy_aware and not kinematic_servo:bias=np.clip(bias+.02*.6*(goal-d.qpos[aq]),-.25,.25)
   rawref=goal+bias
   # Bound reference speed independently of IK; this never changes actual qpos.
   refarm=prev_ref+np.clip(rawref-prev_ref,-.012,.012)
   lo=m.jnt_range[controller.jids[22:29],0]+.002;hi=m.jnt_range[controller.jids[22:29],1]-.002
   refarm=np.clip(refarm,lo,hi);v=np.clip((refarm-prev_ref)/.02,-.6,.6);last_v=.7*last_v+.3*v
   reference[arm]=refarm;future=np.repeat(reference[None],10,axis=0)
   future[:,22:29]=np.clip(refarm[None]+np.arange(10)[:,None]*.1*last_v[None],lo,hi)
   fv=np.zeros_like(future);fv[:,22:29]=last_v
   if c2_reference:
    safe=np.clip(rawref,lo,hi);correction_clipped_cells+=int(np.count_nonzero(abs(safe-rawref)>1e-10))
    try:qfuture,vfuture=smooth_reference.step(safe)
    except RuntimeError as error:fail='reference feasibility stop: '+str(error);break
    reference[arm]=qfuture[0];future[:]=s.DEFAULT_ANGLES;future[:,22:29]=qfuture;fv[:]=0;fv[:,22:29]=vfuture;refarm=qfuture[0]
   tic=time.perf_counter()
   if teleop:
    # Official wrist/head point offsets and FULL root inverse transform.
    fk.qpos[:]=d.qpos;fk.qpos[controller.aq]=reference;mujoco.mj_forward(m,fk)
    rootR=s.rotation(d.qpos[3:7]);positions=[];quats=[]
    for i,(bn,ofs) in enumerate([('left_wrist_yaw_link',[.18,-.025,0]),('right_wrist_yaw_link',[.18,.025,0]),('torso_link',[0,0,.35])]):
     b=m.body(bn).id;R=fk.xmat[b].reshape(3,3).copy();pos=fk.xpos[b].copy()
     if i==1:pos=targetpos.copy();R=targetR.copy()
     positions.append(rootR.T@(pos+R@np.array(ofs)-d.qpos[:3]))
     quat=np.zeros(4);mujoco.mju_mat2Quat(quat,(rootR.T@R).reshape(-1));quats.append(quat)
    controller.step_teleop(d,future,fv,np.tile([1.,0,0,0],(10,1)),np.asarray(positions),np.asarray(quats))
   else:controller.step_policy(d,future,fv,np.tile([1.,0,0,0],(10,1)))
   calls_ms.append(1000*(time.perf_counter()-tic));prev_ref=refarm.copy()
   if policy_aware and step%100==0 and phase!='SETTLE' and not (endpoint_seed and phase=='APPROACH'):
    anchor=refarm.copy() if inverse_anchor else last_goal
    last_goal=inverse_policy.update(d,anchor,prior,targetpos,close_hand,flat_pinch,weight,inverse_incremental)
   if kinematic_servo and step%100==0 and phase!='SETTLE' and not (endpoint_seed and phase=='APPROACH') and not (freeze_close and phase=='CLOSE'):
    fk.qpos[:]=d.qpos;fk.qpos[hq]=close_hand
    desired_q=ik(m,fk,aq,av,targetpos,targetR,d.qpos[aq].copy(),prior,weight,True,flat_pinch,surface_capture,d.xmat[cube].reshape(3,3))
    delta=desired_q-d.qpos[aq];delta*=min(1.,.06/max(abs(delta).max(),1e-12))
    last_goal=np.clip(refarm+delta,lo,hi);servo_updates+=1;servo_max_delta=max(servo_max_delta,float(abs(delta).max()))
   # Native source influence is evidenced by the IK/reference, not claimed necessary.
   ardy_prior_effect.append(float(np.linalg.norm(prior-goal)))
  d.ctrl[:29]=controller.torques(d,arm_gain)
  motor_errors.append(d.qpos[aq]-controller.target[22:29])
  hand=core.OPEN if phase in ['SETTLE','APPROACH','PREGRASP','DESCEND','ALIGN','SETTLE_RELEASE'] else core.blend(core.OPEN,close_hand,e/2) if phase=='CLOSE' else core.blend(close_hand,core.OPEN,e) if phase=='RELEASE' else close_hand
  if no_grip:hand=core.OPEN
  kp,kd=core.gains();ht=kp[core.HAND]*(hand-d.qpos[hq])-kd[core.HAND]*d.qvel[hv]
  d.ctrl[hands]=np.clip(ht,m.actuator_ctrlrange[hands,0],m.actuator_ctrlrange[hands,1])
  ext=max(ext,float(abs(d.xfrc_applied).max()),float(abs(d.qfrc_applied).max()));mujoco.mj_step(m,d)
  forces=np.zeros(3);support=0.
  for k in range(d.ncon):
   c=d.contact[k]
   if cg not in (c.geom1,c.geom2):continue
   other=c.geom2 if c.geom1==cg else c.geom1;f=np.zeros(6);mujoco.mj_contactForce(m,d,k,f)
   if other in pads:forces[pads.index(other)]+=max(0.,f[0])
   if other in supportids:support+=max(0.,f[0])
  poserr=np.linalg.norm(targetpos-d.xpos[wrist]);rerr=np.linalg.norm(rot_error(targetR,d.xmat[wrist].reshape(3,3)))
  if pinch_geometry:
   geo.qpos[:]=d.qpos;geo.qpos[hq]=close_hand;mujoco.mj_forward(m,geo);poserr=np.linalg.norm(targetpos-point(geo));rerr=0.
   if flat_pinch:
    zz=np.array([geo.geom_xpos[m.geom(n).id,2] for n in core.PADS]);rerr=float(zz.max()-zz.min()) # metres, NOT angle
  rot=s.rotation(d.qpos[3:7]);rel=d.xmat[wrist].reshape(3,3).T@(d.xpos[cube]-d.xpos[wrist])
  bottom=d.xpos[cube,2]-.0175*abs(d.xmat[cube].reshape(3,3)[2]).sum()
  rows.append([d.time,*d.xpos[cube],*rel,*forces,support,bottom,np.linalg.norm(d.qpos[:2]-initial_base[:2]),rot[2,2],poserr,rerr,* (d.qpos[aq]-last_goal)])
  if step%20==0:
   frames.append(d.qpos.copy());vels.append(d.qvel.copy());references.append(reference.copy());phases.append(phase)
   motor_targets.append(controller.target.copy());raw_motor_targets.append((s.DEFAULT_ANGLES+controller.last_action[s.M2I]*s.ACTION_SCALE).copy())
  if not np.isfinite(d.qpos).all() or d.qpos[2]<.55 or rot[2,2]<.65:fail='fall/nonfinite';break
  if phase=='SETTLE' and e>=2:change('APPROACH',d.time)
  elif phase=='APPROACH' and e>=10:change('PREGRASP',d.time)
  elif phase=='PREGRASP' and e>=12:change('DESCEND',d.time)
  elif phase=='DESCEND' and e>=8:change('ALIGN',d.time)
  elif phase=='ALIGN':
   near_contact=contact_close and (forces>.05).any() and poserr<.035 and rerr<(.015 if flat_pinch else .10)
   aligned=poserr<capture_radius and rerr<(.012 if flat_pinch else .10) and abs(d.qvel[av]).max()<.15
   alignment_dwell=alignment_dwell+.002 if aligned else 0
   single_contact_dwell=single_contact_dwell+.002 if near_contact else 0
   if alignment_dwell>=.2 or single_contact_dwell>=contact_entry_dwell:change('CLOSE',d.time)
   elif e>max(align_seconds,12 if cart_compensation else 8):fail='alignment timeout';break
  elif phase=='CLOSE':
   contact_dwell=contact_dwell+.002 if (forces>.1).sum()>=2 else 0
   if e>=2 and (contact_dwell>=.2 or no_grip or pad_off):change('LIFT',d.time)
   elif e>5:fail='two-finger contact timeout';break
  elif phase=='LIFT' and e>=8:change('HOLD',d.time);hold_start=d.time
  elif phase=='HOLD' and e>=2:hold_end=d.time;change('RELEASE',d.time);release_start=d.time
  elif phase=='RELEASE' and e>=1:change('SETTLE_RELEASE',d.time)
  elif phase=='SETTLE_RELEASE' and e>=3:break
 else:fail='90s horizon exhausted'
 rows=np.asarray(rows);lift=rows[:,3]-initial_cube[2];contacts=(rows[:,7:10]>.01).sum(axis=1)
 hold=(rows[:,0]>(hold_start or 1e9)+.02)&(rows[:,0]<=(hold_end or -1));h=rows[hold];release=rows[rows[:,0]>(release_start or 1e9)+2]
 slip=float(np.max(np.linalg.norm(h[:,4:7]-h[0,4:7],axis=1))) if len(h) else 1e9
 warnings=(np.array([x.number for x in d.warning])-warnings0).tolist()
 gates=dict(completed=fail is None,hold_7cm=len(h)>0 and lift[hold].min()>=.07,two_fingers=len(h)>0 and contacts[hold].min()>=2,
            no_support=len(h)>0 and h[:,10].max()<.001,clearance_4cm=len(h)>0 and (h[:,11]-.725).min()>=.04,
            slip_1cm=slip<.01,release_drop_6cm=len(h)>0 and len(release)>0 and h[-1,3]-release[:,3].min()>=.06,
            final_supported=rows[-1,10]>.05,final_fingers_off=contacts[-1]==0,no_external=ext==0,no_warnings=not any(warnings),upright=rows[:,13].min()>.9)
 stamp=dict(mujoco_version=mujoco.__version__,sys_executable=__import__('sys').executable,python_version=__import__('sys').version,
            model_sha={'scene':s.sha(scene),'robot':s.sha(out/'g1_free_grasp.xml')},scene_generator_sha=s.sha(__file__),
            library_sha={**controller.model_stamp,'sonic_v11':s.sha(s.__file__),'native_npz':motion.audit['source_npz_sha256'],
                         **{k:v.audit['source_npz_sha256'] for k,v in phase_motions.items()},
                         'reference_filter':s.sha(root/'reference_filter.py'),
                         'policy_reference':s.sha(root/'policy_reference.py'),
                         'grasp_geometry':s.sha(root/'grasp_geometry.py'),
                         **({'endpoint_seed':s.sha(root/'out/pinch-feasibility.json')} if endpoint_seed else {}),
                         'motion_input':s.sha(root/'motion_input.py'),'calibration':s.sha(root/'src/manual_grasp_calibration.npz'),
                         'task_plan':s.sha(root/'task_plan.py'),'source_physics_core':s.sha(core.__file__)},dt=.002)
 result=dict(runtime_stamp=stamp,success=all(bool(v) for v in gates.values()),gates={k:bool(v) for k,v in gates.items()},
             kind=('ARDY original reach shape/posture -> geometric pinch retargeting -> official SONIC '+('pelvis-fixtured' if fixed_base else 'free-base')+' body control + separate contact-gated fingers; no human grasp endpoint joints' if pinch_geometry else 'SONIC teleop-mode calibrated geometry diagnostic; native ARDY arm prior NOT consumed by teleop input' if teleop else 'HYBRID calibrated Cartesian route + original ARDY posture prior -> official SONIC body control + contact-gated fingers'),
             ardy_arm_prior_consumed_by_sonic=not teleop,native_geometry=native_geometry,pinch_geometry=pinch_geometry,native_orientation_frame=native_frame,
             native_path_consumed_by_sonic=native_geometry or pinch_geometry,
             native_ardy_grasp_established=False,human_calibration_used=not pinch_geometry,ardy_nullspace_weight=weight,source=motion.audit,
             position_error_metric='index-pad physical surface contact frame' if surface_capture else 'closed-hand FK thumb/index midpoint' if pinch_geometry else 'wrist frame',surface_capture=surface_capture,
             flat_pinch=flat_pinch,orientation_error_metric='closed-hand FK pad vertical spread in METRES' if flat_pinch else 'wrist rotation rad',
             c2_reference=c2_reference,reference_filter=smooth_reference.audit() if c2_reference else None,correction_clipped_cells=correction_clipped_cells,
             policy_aware_reference=policy_aware,policy_reference=inverse_policy.audit() if policy_aware else None,
             endpoint_branch_seed=endpoint_seed,
             endpoint_seed_selection='minimum native-seed deviation among feasible branches' if endpoint_seed_native else 'minimum geometric residual',
             inverse_reference_anchor='current executed SONIC input reference' if inverse_anchor else 'unexecuted accumulated reference goal',
             inverse_reference_linearization='actual pose + decoded motor target increment' if inverse_incremental else 'absolute decoded motor target FK',
             kinematic_outer_servo=dict(enabled=kinematic_servo,updates=servo_updates,max_reference_increment_rad=servo_max_delta,rate_hz=5,motor_target_override=False,kind='closed-hand actual FK IK delta added to current SONIC input reference'),
             base_fixture=fixed_base,fixture_constraint='pelvis-to-world only; cube is NEVER welded' if fixed_base else None,whole_body_balance_validated=not fixed_base,
             right_arm_pd_kp_scale=arm_gain,right_arm_pd_kd_scale=float(np.sqrt(arm_gain)),decoder_targets_unchanged_by_PD_tuning=True,
             joint_reference_error_definition='actual arm minus virtual SONIC input reference; not necessarily decoder motor setpoint',
             object_localization='simulator-state coordinates during DESCEND/ALIGN/CLOSE; not vision',
             cartesian_compensation=cart_compensation,final_cart_bias_m=cart_bias.tolist(),phase_clips_loaded=phase_clips,
             preclosure_capture_radius_m=capture_radius,final_success_gates_unchanged=True,
             preclosure_contact_close_enabled=contact_close,preclosure_contact_rule='one pad >.05N AND capture-point error<35mm AND flat spread<15mm' if contact_close else None,preclosure_contact_dwell_s=contact_entry_dwell,freeze_reference_during_close=freeze_close,alignment_time_limit_s=align_seconds,
             phase_clips_consumed=sorted(phase_consumed),generated_lift_timewarp='positive vertical excursion normalized to10cm, monotone accumulated; explicit retargeting' if phase_clips else None,
             body_action_override=False,no_grip=no_grip,pad_off=pad_off,compensation=compensation,teleop_mode=teleop,fail_reason=fail,events=events,
             duration_s=d.time,model_load_s=load_s,wall_s=time.monotonic()-start,max_lift_m=float(lift.max()),hold_min_lift_m=float(lift[hold].min()) if len(h) else -1.,
             hold_slip_m=slip,hold_min_contact_bodies=int(contacts[hold].min()) if len(h) else 0,max_drift_m=float(rows[:,12].max()),min_up_z=float(rows[:,13].min()),
             final_wrist_position_error_m=float(rows[-1,14]),
             **({'final_pad_vertical_spread_m':float(rows[-1,15])} if flat_pinch else {'final_wrist_rotation_error_rad':float(rows[-1,15])}),
             right_arm_tracking_rms_rad=float(np.sqrt(np.mean(rows[:,16:23]**2))),max_ik_position_error_m=float(np.max(np.asarray(ik_errors)[:,0])),
             actual_to_decoded_motor_target_rms_rad=float(np.sqrt(np.mean(np.asarray(motor_errors)**2))),
             final_actual_arm_rad=d.qpos[aq].tolist(),final_decoded_motor_target_rad=controller.target[22:29].tolist(),final_virtual_reference_rad=reference[22:29].tolist(),
             max_reference_bias_rad=float(abs(bias).max()),policy_median_ms=float(np.median(calls_ms)),policy_p95_ms=float(np.percentile(calls_ms,95)),
             user_corrections=0,correction_definition='no interactive user text corrections; manually calibrated geometry is a preconfigured constraint, NOT counted as zero human setup',
             peak_external_force=ext,warnings=warnings,sonic=controller.audit(),scene=str(scene))
 np.savez_compressed(out/'trajectory.npz',qpos=frames,qvel=vels,body_reference=references,decoded_motor_target=motor_targets,raw_decoded_motor_target=raw_motor_targets,phase=phases,time=rows[::20,0],fps=25,scene=str(scene),runtime_stamp=json.dumps(stamp))
 columns=['time_s','cube_x_m','cube_y_m','cube_z_m','cube_wrist_x_m','cube_wrist_y_m','cube_wrist_z_m','thumb_force_N','index_force_N','middle_force_N','support_force_N','cube_bottom_m','base_xy_drift_m','base_up_z','closed_center_error_m' if pinch_geometry else 'wrist_position_error_m','pad_vertical_spread_m' if flat_pinch else 'wrist_rotation_error_rad']+['actual_minus_virtual_ref_'+m.joint(int(j)).name+'_rad' for j in controller.jids[22:29]]
 result['telemetry_schema']=dict(path='telemetry.csv.gz',columns=columns,physics_hz=500,format='gzip CSV; 9 significant digits; full result/NPZ floats preserved',finger_contact_white_list=core.PADS)
 with gzip.open(out/'telemetry.csv.gz','wt') as f:
  f.write('# runtime_stamp='+json.dumps(stamp)+'\n# '+','.join(columns)+'\n');np.savetxt(f,rows,delimiter=',',fmt='%.9g')
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ['source','sonic','runtime_stamp']},indent=2));return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--weight',type=float,default=.03);p.add_argument('--no-grip',action='store_true');p.add_argument('--pad-off',action='store_true');p.add_argument('--no-compensation',action='store_true');p.add_argument('--teleop',action='store_true');p.add_argument('--native-geometry',action='store_true');p.add_argument('--pinch-geometry',action='store_true');p.add_argument('--cart-compensation',action='store_true');p.add_argument('--phase-clips',action='store_true');p.add_argument('--capture-radius',type=float,default=.007);p.add_argument('--flat-pinch',action='store_true');p.add_argument('--c2-reference',action='store_true');p.add_argument('--policy-aware',action='store_true');p.add_argument('--endpoint-seed',action='store_true');p.add_argument('--arm-gain',type=float,default=1.)
 p.add_argument('--fixed-base',action='store_true');p.add_argument('--inverse-anchor',action='store_true');p.add_argument('--endpoint-seed-native',action='store_true');p.add_argument('--inverse-incremental',action='store_true');p.add_argument('--kinematic-servo',action='store_true');p.add_argument('--contact-close',action='store_true');p.add_argument('--align-seconds',type=float,default=8.);p.add_argument('--surface-capture',action='store_true');p.add_argument('--contact-entry-dwell',type=float,default=.2);p.add_argument('--freeze-close',action='store_true');a=p.parse_args()
 assert not a.endpoint_seed_native or a.endpoint_seed
 assert not a.inverse_anchor or a.policy_aware
 assert not a.inverse_incremental or a.policy_aware
 assert 0<=a.weight<=.1
 assert .005<=a.capture_radius<=.025
 assert not a.flat_pinch or a.pinch_geometry
 assert 1<=a.arm_gain<=4
 assert 8<=a.align_seconds<=25
 assert .02<=a.contact_entry_dwell<=.2
 run(a.name,a.weight,a.no_grip,a.pad_off,not a.no_compensation,a.teleop,a.native_geometry,a.pinch_geometry,a.cart_compensation,a.phase_clips,a.capture_radius,a.flat_pinch,a.c2_reference,a.policy_aware,a.endpoint_seed,a.arm_gain,a.fixed_base,a.inverse_anchor,a.endpoint_seed_native,a.inverse_incremental,a.kinematic_servo,a.contact_close,a.align_seconds,a.surface_capture,a.contact_entry_dwell,a.freeze_close)
