"""Finite ARDY-prior/SONIC v1.1 whole-hand side-grasp diagnostic.

Free floating robot and free object; original hand geometry and palm collide.
Native mode disables artificial sphere pads. ONLY ctrl is written during simulation. Reference IK is
not motor IK: SONIC alone decodes all29 body targets. Hand PD is separate.
"""
from pathlib import Path
import sys,os,json,time,hashlib,argparse,shutil
import numpy as np,mujoco
import wholehand_side as w
import xml.etree.ElementTree as ET
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation,Slerp
R=Path(__file__).resolve().parent
WEIGHTS={name:w.sonic.sha(Path(w.sonic.__file__).parent/'sonic_v11'/name) for name in ['model_encoder.onnx','model_decoder.onnx','observation_config.yaml']}

def runtime_stamp(m,p,out,pdir):
 return {'mujoco_version':mujoco.__version__,'sys_executable':sys.executable,'python_version':sys.version,
  'model_sha':{'robot':w.sha(out/'robot.xml'),'scene':w.sha(out/'scene.xml')},
  'scene_generator_sha':w.sha(R/'batch_plan.py'),'library_sha':{'ardy_npz':p['ardy_source']['source_npz_sha256'],
  'sonic_module':w.sha(w.sonic.__file__),'sonic_models':WEIGHTS,'plan':w.sha(pdir/'plan.json')},'source_sha':w.sha(__file__),
  'planner_sha':w.sha(w.__file__),'model_xml_sha':{'robot':w.sha(out/'robot.xml'),'scene':w.sha(out/'scene.xml')},
  'model_asset_manifest_sha':w.sha(R/'model-assets.json') if (R/'model-assets.json').exists() else 'pilot-before-asset-freeze',
  'dt':float(m.opt.timestep),'impratio':10,'margin_m':.001,'solref':[.02,1],'plan':str(pdir),
  'in_memory_geometry_sha':hashlib.sha256(m.geom_contype.tobytes()+m.geom_conaffinity.tobytes()+m.geom_margin.tobytes()+m.geom_solref.tobytes()+m.dof_armature.tobytes()).hexdigest(),
  'ardy_source':p['ardy_source'],'root_x_initial_m':float(p.get('root_x',0))}

def save_npz(path,rows,stamp):
 values={key:np.array(value) for key,value in rows.items()}
 values['runtime_stamp_json']=np.array(json.dumps(stamp,sort_keys=True))
 np.savez_compressed(path,**values)

def refusal_idle(m,d,hq,hv,out,stamp,reason):
 """A real safe standing episode, NOT execution of a rejected grasp path."""
 policy=w.sonic.SonicV11(m);qf=np.tile(w.sonic.DEFAULT_ANGLES,(10,1));vf=np.zeros((10,29));quat=np.tile([1.,0,0,0],(10,1))
 hand=d.qpos[hq].copy();wrist=m.body('right_wrist_yaw_link').id;cb=m.body('red_cube').id;initz=float(d.xpos[cb,2])
 rows={key:[] for key in ['time','qpos','qvel','cube_pos','wrist_pos','ctrl','phase']}
 for step in range(10000):
  if step%20==0:policy.step_policy(d,qf,vf,quat)
  d.ctrl[:29]=policy.torques(d,right_arm_scale=3.,gravity_arm_scale=1.,right_arm_damping_scale=2.)
  for start,end,goal,kp,kd in [(29,36,np.zeros(7),8.,.7),(36,43,hand,40.,2.)]:
   joints=m.actuator_trnid[start:end,0];q=m.jnt_qposadr[joints];v=m.jnt_dofadr[joints]
   d.ctrl[start:end]=np.clip(kp*(goal-d.qpos[q])-kd*d.qvel[v],m.actuator_ctrlrange[start:end,0],m.actuator_ctrlrange[start:end,1])
  mujoco.mj_step(m,d)
  if step%20==0:
   for key,val in {'time':step*.001,'qpos':d.qpos.copy(),'qvel':d.qvel.copy(),'cube_pos':d.xpos[cb].copy(),
                   'wrist_pos':d.xpos[wrist].copy(),'ctrl':d.ctrl.copy(),'phase':'PLAN_REFUSED_SAFE_HOLD'}.items():rows[key].append(val)
  if not np.isfinite(d.qpos).all():break
 save_npz(out/'trajectory.npz',rows,stamp)
 result={'success':False,'classification':'planning_refused','reason':reason,'physics_run_kind':'safe_standing_after_planning_refusal',
  'grasp_path_executed':False,'duration_s':float(d.time),'hold_safe_steps':0,'hold_support_steps':0,
  'max_lift_m':float(np.max(np.array(rows['cube_pos'])[:,2])-initz),'native_mesh_only':True,'runtime_stamp':stamp,'sonic':policy.audit()}
 (out/'result.json').write_text(json.dumps(result,indent=2));print('RESULT',json.dumps(result),flush=True)

def smooth(u):u=np.clip(u,0,1);return u*u*(3-2*u)
def rotations(A,B,u):return Slerp([0,1],Rotation.from_matrix([A,B]))([float(u)]).as_matrix()[0]
def body_geoms(m):
 return [g for g in range(m.ngeom) if m.body(int(m.geom_bodyid[g])).name.startswith(('right_hand_','right_wrist_','right_elbow','right_shoulder')) and m.geom_contype[g]]
def harmful(m,d,hand,fixture):
 rows=[]
 for c in d.contact:
  a,b=int(c.geom1),int(c.geom2)
  if (a in hand and b in fixture) or (b in hand and a in fixture):
   if c.dist<-.0002:rows.append([m.geom(a).name,m.geom(b).name,float(c.dist)])
 return rows
def main(a):
 pdir=R/'out'/a.plan;p=json.loads((pdir/'plan.json').read_text())
 out=R/'out'/a.name;out.mkdir()
 for n in ['robot.xml','scene.xml']:shutil.copy2(pdir/n,out/n)
 if a.native_mesh:
  tree=ET.parse(out/'robot.xml')
  for g in tree.iter('geom'):
   if g.get('name') in w.PADS:g.set('contype','0');g.set('conaffinity','0');g.set('rgba','0 0 0 0')
  tree.write(out/'robot.xml',encoding='utf8')
 m=mujoco.MjModel.from_xml_path(str(out/'scene.xml'));d=mujoco.MjData(m);fk=mujoco.MjData(m)
 bq=m.jnt_qposadr[m.actuator_trnid[:29,0]];bv=m.jnt_dofadr[m.actuator_trnid[:29,0]]
 hj=m.actuator_trnid[36:43,0];hq=m.jnt_qposadr[hj]
 aq,av,hv,lim,idx,pads,cube,table,bones=w.setup(m,d,bq,hj,hq)
 wrist=m.body('right_wrist_yaw_link').id;cb=m.body('red_cube').id
 # Contact recipe ported as an explicitly labelled experiment, not assumed real.
 m.opt.timestep=.001;m.opt.impratio=10
 for g in [cube]+body_geoms(m):m.geom_margin[g]=.001;m.geom_solref[g,:2]=[.02,1]
 # Add controller inertia only in this model, respecting physical effort limits.
 m.dof_armature[hv]=.1
 rootx=float(p.get('root_x',0))
 d.qpos[:7]=[rootx,0,.788740,1,0,0,0];d.qpos[bq]=w.sonic.DEFAULT_ANGLES
 initialhand=np.array([0.,-.7,-1.5,.5,.5,.5,.5]);d.qpos[hq]=initialhand
 mujoco.mj_forward(m,d);fk.qpos[:]=d.qpos
 stamp=runtime_stamp(m,p,out,pdir)
 (out/'episode_contract.json').write_text(json.dumps({'runtime_stamp':stamp,'native_mesh_only':a.native_mesh,'initial_qpos':d.qpos.tolist(),
  'right_arm_gravity_feedforward_scale':a.gravity_arm_scale,'physical_gravity_m_s2':m.opt.gravity.tolist(),
  'no_grip':a.no_grip,'wrist_servo':a.wrist_servo,'trial_config':p.get('trial_config',{}),
  'active_hand_geoms':[{'name':m.geom(g).name,'body':m.body(int(m.geom_bodyid[g])).name,
    'contype':int(m.geom_contype[g]),'conaffinity':int(m.geom_conaffinity[g])} for g in range(m.ngeom)
    if m.body(int(m.geom_bodyid[g])).name.startswith(('left_hand_','right_hand_','left_wrist_','right_wrist_'))],
  'neq':int(m.neq),'nmocap':int(m.nmocap),'nq':int(m.nq),'nv':int(m.nv),'nu':int(m.nu)},indent=2))
 neutral=d.qpos[aq].copy();startpos=d.xpos[wrist].copy();startR=d.xmat[wrist].reshape(3,3).copy()
 terminalarm=np.array(p['arm']);openhand=np.array(p['closed_hand'])
 fk.qpos[aq]=terminalarm;fk.qpos[hq]=openhand;mujoco.mj_forward(m,fk)
 terminalpos=fk.xpos[wrist].copy();terminalR=fk.xmat[wrist].reshape(3,3).copy()
 gaprows=w.clearances(m,fk,bones,cube,table)
 terminalcheck=harmful(m,fk,body_geoms(m),[cube,table])
 # A gap-positive approach must be solved before any dynamic experiment.
 if not p.get('geometry_pass',True) or gaprows.min()<0 or terminalcheck:
  result={'status':'REFUSED_STATIC','gaps':gaprows.tolist(),'contacts':terminalcheck,'success':False}
  (out/'planning_refusal.json').write_text(json.dumps(result,indent=2));refusal_idle(m,d,hq,hv,out,stamp,'REFUSED_STATIC');return
 targets=np.array(p['best']['targets']);axis=p['best']['axis']
 targets[0,axis]+=p['pad_gap_m']+.001;targets[1:,axis]-=p['pad_gap_m']+.001
 def finger_res(q):
  fk.qpos[hq]=q;mujoco.mj_forward(m,fk)
  return ((fk.geom_xpos[pads]-targets)*1000).ravel()
 closedfit=least_squares(finger_res,openhand,bounds=(lim[7:,0]+.003,lim[7:,1]-.003),max_nfev=300)
 closedhand=closedfit.x;closederror=float(np.max(np.linalg.norm(fk.geom_xpos[pads]-targets,axis=1)))
 # Raised rotation + raised traverse + vertical final approach at wide opening.
 points=[(0.,startpos,startR,neutral,initialhand),
         (1.,startpos,startR,neutral,initialhand),
         (5.,np.array([rootx+(.02 if a.retract_raise else .10),-.27,1.03]),startR,None,initialhand),
         (9.,np.array([rootx+.13,-.28,1.03]),terminalR,None,openhand),
         (13.,terminalpos+np.array([0,0,.13]),terminalR,None,openhand),
         (18.,terminalpos,terminalR,terminalarm,openhand),
         (21.,terminalpos,terminalR,terminalarm,openhand)]
 arm=[];hand=[];wp=[];phase=[];prev=neutral.copy();pathcontacts=[];maxikerror=0.
 handgeoms=body_geoms(m);fixtures=[cube,table]
 for t in np.arange(0,21.00001,.02):
  segment=min(next((i for i in range(len(points)-1) if points[i][0]<=t<=points[i+1][0]),len(points)-2),len(points)-2)
  A,B=points[segment],points[segment+1];u=smooth((t-A[0])/(B[0]-A[0]));pos=(1-u)*A[1]+u*B[1];rot=rotations(A[2],B[2],u);h=(1-u)*A[4]+u*B[4]
  fk.qpos[:]=d.qpos;fk.qpos[hq]=h
  def ik(q):
   fk.qpos[aq]=q;mujoco.mj_forward(m,fk)
   r=Rotation.from_matrix(rot@fk.xmat[wrist].reshape(3,3).T).as_rotvec()
   return np.r_[(fk.xpos[wrist]-pos)*1000,r*100,(q-prev)*.02]
  if t<1:q=neutral.copy()
  else:q=least_squares(ik,prev,bounds=(lim[:7,0]+.003,lim[:7,1]-.003),max_nfev=30).x
  ik(q);maxikerror=max(maxikerror,float(np.linalg.norm(fk.xpos[wrist]-pos)))
  cs=harmful(m,fk,handgeoms,fixtures)
  if cs:pathcontacts.append({'time':float(t),'contacts':cs})
  arm.append(q.copy());hand.append(h);wp.append(pos);phase.append(segment);prev=q.copy()
 arm=np.array(arm);hand=np.array(hand);wp=np.array(wp)
 # Global time scaling preserves the collision-checked joint path while reducing
 # its joint speed, instead of clipping individual joint references.
 oldtimes=np.arange(len(arm))*.02
 newtimes=np.arange(0,oldtimes[-1]*a.time_scale+1e-8,.02)
 arm=np.stack([np.interp(newtimes/a.time_scale,oldtimes,arm[:,j]) for j in range(7)],axis=1)
 hand=np.stack([np.interp(newtimes/a.time_scale,oldtimes,hand[:,j]) for j in range(7)],axis=1)
 wp=np.stack([np.interp(newtimes/a.time_scale,oldtimes,wp[:,j]) for j in range(3)],axis=1)
 T=float(newtimes[-1]);end=T+11
 reference=np.tile(w.sonic.DEFAULT_ANGLES,(len(arm),1));reference[:,22:29]=arm
 reference_velocity=np.gradient(reference,.02,axis=0)
 maxspeed=float(np.max(abs(np.diff(arm,axis=0)/.02)))
 planstamp={'geometry_metric':'convex hull SAT independently checked at terminal + mj_forward actual contact pairs along 20ms references',
  'open_terminal_gaps':gaprows.tolist(),'closed_pad_error_m':closederror,'max_ik_position_error_m':maxikerror,'max_reference_joint_speed_rad_s':maxspeed,
  'path_contact_frames':len(pathcontacts),'path_first_contacts':pathcontacts[:8],'times_s':[x[0]*a.time_scale for x in points],'global_time_scale':a.time_scale,'joint_limits':lim.tolist()}
 (out/'execution_plan.json').write_text(json.dumps({**planstamp,'runtime_stamp':stamp},indent=2));np.savez_compressed(out/'reference.npz',body=reference,hand=hand,wrist=wp,runtime_stamp_json=np.array(json.dumps(stamp,sort_keys=True)))
 if a.plan_only or pathcontacts or maxikerror>.003 or maxspeed>2.:
  result={'status':'PLAN_ONLY' if a.plan_only else 'REFUSED_PATH','success':False,**planstamp}
  (out/'planning_refusal.json').write_text(json.dumps(result,indent=2))
  if a.plan_only:print(json.dumps(result));return
  refusal_idle(m,d,hq,hv,out,stamp,'REFUSED_PATH');return
 policy=w.sonic.SonicV11(m);dt=m.opt.timestep;stride=20
 rows={k:[] for k in ['time','qpos','qvel','body_reference','hand_reference','decoded_target','ctrl','cube_pos','wrist_pos','pad_forces','other_hand_force','table_force','phase','hand_saturation']}
 initz=float(d.xpos[cb,2]);events=[];maxlift=0.;holdgood=[];lift0=None;relative0=None;maxslip=0.;firstbone=None
 liftarm=None;currentarm=arm[-1].copy();currentpos=terminalpos.copy()
 mode='REACH';reason='timeout';startwall=time.time();offset=np.zeros(7);local0=None;maxlocalslip=0.;localhold0=None;maxholdlocalslip=0.
 jacp=np.zeros((3,m.nv));jacr=np.zeros((3,m.nv));hold_opposition=[];runtime_contacts=[];joint_violation=0.;self_contact_count=0
 hold_safety=[];preclose_collision_peak=0.;foot_min=np.array([1e9,1e9]);nontable_peak=0.
 for step in range(int(end/dt)):
  t=step*dt
  if t<T:
   i=min(round(t/.02),len(arm)-1);refhand=hand[i];futureidx=np.clip(i+np.arange(10)*5,0,len(arm)-1)
   qf=reference[futureidx];vf=reference_velocity[futureidx]
   currentarm=arm[i].copy();mode='REACH'
  else:
   # Stop changing ARDY reference, keep SONIC running for arm/body hold.
   qf=np.tile(w.sonic.DEFAULT_ANGLES,(10,1));qf[:,22:29]=currentarm;vf=np.zeros((10,29))
   if t<T+3:mode='CLOSE';refhand=openhand if a.no_grip else (1-smooth((t-T)/3))*openhand+smooth((t-T)/3)*closedhand
   elif t<T+4:mode='GRIP_DWELL';refhand=openhand if a.no_grip else closedhand
   else:
    refhand=openhand if a.no_grip else closedhand
    if lift0 is None:lift0=t;relative0=d.xpos[cb]-d.xpos[wrist];mode='TEST_LIFT'
    height=.015*smooth((t-T-4)/1.5) if t<T+5.5 else .015+.085*smooth((t-T-5.5)/3)
    currentpos=terminalpos+np.array([0,0,height]);fk.qpos[:]=d.qpos
    if step%stride==0:
     seed=currentarm.copy()
     def liftik(q):
      fk.qpos[aq]=q;mujoco.mj_forward(m,fk)
      return np.r_[(fk.xpos[wrist]-currentpos)*1000,Rotation.from_matrix(terminalR@fk.xmat[wrist].reshape(3,3).T).as_rotvec()*100,(q-seed)*.1]
     currentarm=least_squares(liftik,seed,bounds=(lim[:7,0]+.003,lim[:7,1]-.003),max_nfev=25).x
    qf[:,22:29]=currentarm;mode='TEST_LIFT' if t<T+5.5 else ('LIFT' if t<T+8.5 else 'HOLD')
  if a.wrist_servo and t>=T-8 and step%stride==0:
   desired=wp[min(round(t/.02),len(wp)-1)] if t<T else currentpos
   mujoco.mj_jacBody(m,d,jacp,jacr,wrist)
   e=np.r_[desired-d.xpos[wrist],Rotation.from_matrix(terminalR@d.xmat[wrist].reshape(3,3).T).as_rotvec()*.1]
   J=np.r_[jacp[:,av],jacr[:,av]*.1]
   delta=np.linalg.solve(J.T@J+np.eye(7)*.002,J.T@e)
   offset=np.clip(offset+np.clip(delta*.10,-.01,.01),-.25,.25)
  if a.wrist_servo:
   qf=qf.copy();qf[:,22:29]=np.clip(qf[:,22:29]+offset,lim[:7,0]+.003,lim[:7,1]-.003)
  if step%stride==0:
   policy.step_policy(d,qf,vf,np.tile([1.,0,0,0],(10,1)))
  d.ctrl[:29]=policy.torques(d,right_arm_scale=3.,gravity_arm_scale=a.gravity_arm_scale,right_arm_damping_scale=2.)
  leftj=m.actuator_trnid[29:36,0];leftq=m.jnt_qposadr[leftj];leftv=m.jnt_dofadr[leftj]
  d.ctrl[29:36]=np.clip(-8*d.qpos[leftq]-.7*d.qvel[leftv],m.actuator_ctrlrange[29:36,0],m.actuator_ctrlrange[29:36,1])
  rawhand=40*(refhand-d.qpos[hq])-2*d.qvel[hv]
  d.ctrl[36:43]=np.clip(rawhand,m.actuator_ctrlrange[36:43,0],m.actuator_ctrlrange[36:43,1])
  mujoco.mj_step(m,d)
  pf,other,tableforce,depth,cs=w.contact_summary(m,d,pads,cube,bones)
  tf=sum(c['normal_N'] for c in cs if 'right_hand_thumb' in c['body']);of=sum(c['normal_N'] for c in cs if 'right_hand_index' in c['body'] or 'right_hand_middle' in c['body'])
  local=d.xmat[wrist].reshape(3,3).T@(d.xpos[cb]-d.xpos[wrist])
  maxlift=max(maxlift,float(d.xpos[cb,2]-initz))
  if other>.1 and firstbone is None:firstbone={'time':float(t),'phase':mode,'contacts':cs};events.append(firstbone)
  if relative0 is not None:
   if local0 is None:local0=local.copy()
   maxslip=max(maxslip,float(np.linalg.norm((d.xpos[cb]-d.xpos[wrist])-relative0)));maxlocalslip=max(maxlocalslip,float(np.linalg.norm(local-local0)))
  if mode=='HOLD':
   if localhold0 is None:localhold0=local.copy()
   maxholdlocalslip=max(maxholdlocalslip,float(np.linalg.norm(local-localhold0)))
   holdgood.append(bool(d.xpos[cb,2]-initz>=.07 and tableforce<.05 and np.count_nonzero(pf>.1)>=2));hold_opposition.append(tf>.1 and of>.1)
  feet=np.zeros(2);nonfoot=0.;robottable=0.
  floor=m.geom('floor').id
  for i,c in enumerate(d.contact):
   f=np.zeros(6);mujoco.mj_contactForce(m,d,i,f);F=max(0.,float(f[0]))
   if floor in [c.geom1,c.geom2]:
    g=c.geom2 if c.geom1==floor else c.geom1;name=m.body(int(m.geom_bodyid[g])).name
    if name.startswith('left_ankle'):feet[0]+=F
    elif name.startswith('right_ankle'):feet[1]+=F
    elif name not in ['world','red_cube']:nonfoot+=F
   if table in [c.geom1,c.geom2]:
    g=c.geom2 if c.geom1==table else c.geom1;name=m.body(int(m.geom_bodyid[g])).name
    if name not in ['world','red_cube','grasp_table']:robottable+=F
  if mode=='HOLD':
   foot_min=np.minimum(foot_min,feet);nontable_peak=max(nontable_peak,nonfoot,robottable)
   hold_safety.append(bool(d.xpos[cb,2]-initz>=.07 and tableforce<.05 and tf>.1 and of>.1 and feet.min()>1 and nonfoot<.05 and robottable<.05))
  if t<T:preclose_collision_peak=max(preclose_collision_peak,other+sum(pf))
  joints=m.actuator_trnid[:,0];qq=d.qpos[m.jnt_qposadr[joints]]
  joint_violation=max(joint_violation,float(np.max(np.maximum(m.jnt_range[joints,0]-qq,qq-m.jnt_range[joints,1]))))
  for c in d.contact:
   if m.geom_bodyid[c.geom1] in m.geom_bodyid[bones] and m.geom_bodyid[c.geom2] in m.geom_bodyid[bones]:self_contact_count+=1
  if step%20==0:
   for k,val in {'time':t,'qpos':d.qpos.copy(),'qvel':d.qvel.copy(),'body_reference':qf[0].copy(),'hand_reference':refhand.copy(),
    'decoded_target':policy.target.copy(),'ctrl':d.ctrl.copy(),'cube_pos':d.xpos[cb].copy(),'wrist_pos':d.xpos[wrist].copy(),
    'pad_forces':pf,'other_hand_force':other,'table_force':tableforce,'phase':mode,'hand_saturation':int(np.count_nonzero(abs(rawhand)>m.actuator_ctrlrange[36:43,1]))}.items():rows[k].append(val)
   runtime_contacts.append({'time':t,'phase':mode,'thumb_load_N':tf,'index_middle_load_N':of,'cube_contacts':cs})
  if step%1000==0:print(json.dumps({'time':round(t,3),'phase':mode,'lift_mm':round(1000*(d.xpos[cb,2]-initz),2),'pads_N':pf.tolist(),'bones_N':other,'root_z':float(d.qpos[2])}),flush=True)
  if step%5000==0:save_npz(out/'checkpoint.npz',rows,stamp)
  if not np.isfinite(d.qpos).all() or d.qpos[2]<.5 or np.linalg.norm(d.qpos[:2])>.35:reason='robot_instability';break
  if t>T+2 and d.xpos[cb,2]<.6:reason='object_fell';break
  if not a.no_grip and maxlift<.003 and t>=T+6:reason='no_test_lift';break
  if time.time()-startwall>700:reason='wall_clock_limit';break
 else:reason='complete'
 save_npz(out/'trajectory.npz',rows,stamp)
 (out/'contact_frames.json').write_text(json.dumps(runtime_contacts))
 legacy_success=bool(reason=='complete' and len(holdgood)>=2000 and all(holdgood) and maxslip<=.01)
 strict_v2=bool(reason=='complete' and len(hold_safety)>=2000 and all(hold_safety) and maxlocalslip<=.01 and joint_violation<.002)
 result={'success':strict_v2,'classification':'physics_success' if strict_v2 else 'physics_failure','grasp_path_executed':True,
  'success_gate_version':'wholehand-v2-wristlocal-support','legacy_worldvector_success':legacy_success,'reason':reason,
  'max_lift_m':maxlift,'max_slip_since_lift_m':maxslip,'hold_pass_steps':sum(holdgood),'hold_steps':len(holdgood),'negative_control':a.no_grip,
  'basic_lift_achieved':bool(len(hold_safety)>=2000 and all(hold_safety)),
  'native_mesh_only':a.native_mesh,'retract_raise':a.retract_raise,'hold_safe_steps':sum(hold_safety),'hold_support_steps':len(hold_safety),
  'hold_each_foot_min_N':foot_min.tolist(),'hold_nonfoot_floor_or_robot_table_peak_N':nontable_peak,'preclose_cube_contact_peak_N':preclose_collision_peak,
  'hold_opposing_load_steps':sum(hold_opposition),'max_wristlocal_slip_alllift_m':maxlocalslip,'max_wristlocal_slip_hold_m':maxholdlocalslip,
  'wrist_reference_servo':a.wrist_servo,'max_servo_offset_rad':float(abs(offset).max()),'max_joint_limit_violation_rad':joint_violation,'self_contact_samples':self_contact_count,
  'duration_s':float(d.time),'wall_seconds':time.time()-startwall,'first_bone_contact':firstbone,'events':events,'execution_plan':planstamp,
  'scope':'ARDY right-arm frame prior + explicit reference-space wrist IK; SONIC all29 decoded motor targets; independent seven-joint finger PD. NOT native ARDY fullbody.',
  'no_cheats':{'free_base':bool(m.jnt_type[0]==mujoco.mjtJoint.mjJNT_FREE),
   'free_object':bool(m.jnt_type[m.body_jntadr[cb]]==mujoco.mjtJoint.mjJNT_FREE),'neq':int(m.neq),'nmocap':int(m.nmocap),
   'object_actuator_count':int(sum(m.jnt_bodyid[int(j)]==cb for j in m.actuator_trnid[:,0])),
   'object_write_evidence':'source-audited controller loop writes ctrl only; zero value is a source contract, not a runtime write hook',
   'object_state_writes_after_init':0,'xfrc_applied_max':float(abs(d.xfrc_applied).max()),'qfrc_applied_max':float(abs(d.qfrc_applied).max())},
  'sonic':policy.audit(),'gravity_arm_scale':a.gravity_arm_scale,'trial_config':p.get('trial_config',{}),
  'finger_controller':{'kp':40,'kd':2,'armature':.1,'original_effort_limits':m.actuator_ctrlrange[36:43].tolist()},
  'runtime_stamp':stamp,'synthetic_pads':'DISABLED: inherited spheres visual markers only; seven original right collision geoms and palm/wrist remain physical'}
 (out/'result.json').write_text(json.dumps(result,indent=2));print('RESULT',json.dumps(result),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--name',required=True);p.add_argument('--plan-only',action='store_true');p.add_argument('--no-grip',action='store_true');p.add_argument('--time-scale',type=float,default=2.);p.add_argument('--wrist-servo',action='store_true');p.add_argument('--native-mesh',action='store_true');p.add_argument('--retract-raise',action='store_true');p.add_argument('--gravity-arm-scale',type=float,choices=[0.,1.],default=1.);a=p.parse_args()
 assert 1<=a.time_scale<=4
 assert a.native_mesh,'all batch tests require native hand physics and no spherical pads'
 assert all(x.replace('_','').replace('-','').isalnum() for x in [a.name,a.plan]);main(a)
