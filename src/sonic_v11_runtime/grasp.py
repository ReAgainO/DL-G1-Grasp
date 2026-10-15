"""Event-gated physical grasp; hybrid calibrated task route + ARDY posture prior."""
import argparse,json,time
from pathlib import Path
import mujoco,numpy as np
import trajectory as tr
import control
import source_physics_core as core
from task_plan import rot_error

def simulate(root,plan_path,name,no_grip=False,pad_off=False):
 start=time.monotonic();root=Path(root);out=root/'out'/name;out.mkdir()
 for n in ['ff327','ff314']:
  assert json.loads((root/'out'/n/'result.json').read_text())['success'],'Stage2 gate not passed'
 p=np.load(plan_path,allow_pickle=False);meta=json.loads(str(p['metadata']))
 assert meta['success'],'Task kinematic gates not passed'
 scene=core.prepare_model(root/'src/g1',out,[.267,-.118],.7745,True)
 m,d,ids,aq,av,qa,va,ix=tr.robot(scene)
 assert m.neq==0 and (m.jnt_type==mujoco.mjtJoint.mjJNT_FREE).sum()==1
 st=tr.stamp(scene);st['scene_generator_sha']=tr.sha(__file__)
 st['library_sha'].update(task_plan_npz=tr.sha(plan_path),grasp_py=tr.sha(__file__),control_py=tr.sha(control.__file__),
                         calibration_npz=tr.sha(root/'src/manual_grasp_calibration.npz'),
                         ardy_source_csv=tr.sha(root/'src/guided_s42.csv'))
 if pad_off:
  for n in core.PADS:
   g=m.geom(n).id;m.geom_contype[g]=0;m.geom_conaffinity[g]=0
  st['collision_override']='three finger pads disabled; physical negative control'
 cube=m.body('red_cube').id;wrist=m.body('right_wrist_yaw_link').id
 pads=[m.geom(n).id for n in core.PADS];cg=m.geom('red_cube_geom').id
 supports={m.geom(n).id for n in ['table_top','cube_pedestal_geom','floor']}
 handnames=[a.get('name') for a in core.ET.parse(root/'src/g1/g1_29dof_with_hand.xml').find('actuator')]
 handids=np.array([m.actuator(handnames[i]).id for i in core.HAND])
 d.qpos[aq]=p['down_q'][0];mujoco.mj_forward(m,d)
 initcube=d.xpos[cube].copy();base=d.body('pelvis').xpos.copy()
 target=d.qpos[qa].copy();tv=np.zeros(m.nu);ta=np.zeros(m.nu);fk=mujoco.MjData(m)
 phase='PREGRASP';phase_start=0.;aligned=0.;contact_dwell=0.;events=[{'phase':phase,'time_s':0.}]
 rows=[];frames=[];vels=[];armtargets=[];phases=[];sat=0;warnings=np.array([w.number for w in d.warning]);peakext=0.
 hold_start=None;hold_end=None;release_start=None;maxtrack=0.;fail_reason=None
 phase_duration=float(meta['phase_duration_s'])
 def change(new,t):
  nonlocal phase,phase_start
  phase=new;phase_start=t;events.append({'phase':new,'time_s':float(t)})
 for step in range(45000): # 90s hard simulation horizon
  t=step*.002;elapsed=t-phase_start
  if phase in ('PREGRASP','DESCEND','ALIGN','CLOSE'):
   arr='down';k=0 if phase=='PREGRASP' else min(int(elapsed/.002),len(p['down_q'])-1) if phase=='DESCEND' else len(p['down_q'])-1
  else:
   arr='up';k=min(int(elapsed/.002),len(p['up_q'])-1) if phase=='LIFT' else len(p['up_q'])-1
  target[ids]=p[arr+'_q'][k];tv[ids]=p[arr+'_v'][k] if phase in ('DESCEND','LIFT') else 0;ta[ids]=p[arr+'_a'][k] if phase in ('DESCEND','LIFT') else 0
  if phase in ('PREGRASP','DESCEND','ALIGN'):hand=core.OPEN
  elif phase=='CLOSE':hand=core.blend(core.OPEN,core.CLOSED,elapsed/2)
  elif phase in ('LIFT','HOLD'):hand=core.CLOSED
  else:hand=core.blend(core.CLOSED,core.OPEN,elapsed) if phase=='RELEASE' else core.OPEN
  if no_grip or pad_off:hand=core.OPEN if no_grip else hand
  target[handids]=hand;target=np.clip(target,m.jnt_range[m.actuator_trnid[:,0],0],m.jnt_range[m.actuator_trnid[:,0],1])
  ctrl,tau=control.command(m,d,qa,va,ix,ids,av,target,tv,ta,'feedforward')
  sat+=int(np.count_nonzero(abs(ctrl[ids]-tau[ids])>1e-10));d.ctrl[:]=ctrl
  peakext=max(peakext,float(np.max(abs(d.xfrc_applied))),float(np.max(abs(d.qfrc_applied))))
  mujoco.mj_step(m,d)
  if not np.isfinite(d.qpos).all():raise RuntimeError('Nonfinite state')
  forces=np.zeros(3);support=0.
  for i in range(d.ncon):
   c=d.contact[i]
   if cg not in (c.geom1,c.geom2):continue
   other=c.geom2 if c.geom1==cg else c.geom1;f=np.zeros(6);mujoco.mj_contactForce(m,d,i,f)
   if other in pads:forces[pads.index(other)]+=max(0.,f[0])
   if other in supports:support+=max(0.,f[0])
  rel=d.xmat[wrist].reshape(3,3).T@(d.xpos[cube]-d.xpos[wrist])
  bottom=d.xpos[cube,2]-.0175*np.abs(d.xmat[cube].reshape(3,3)[2]).sum()
  error=d.qpos[aq]-target[ids];maxtrack=max(maxtrack,float(np.max(abs(error))))
  rows.append([d.time,*d.xpos[cube],*rel,*forces,support,bottom,np.linalg.norm(d.body('pelvis').xpos-base),*error])
  if step%20==0:
   frames.append(d.qpos.copy());vels.append(d.qvel.copy());armtargets.append(target[ids].copy());phases.append(phase)
  if phase=='PREGRASP' and elapsed>=1:change('DESCEND',d.time)
  elif phase=='DESCEND' and elapsed>=phase_duration:change('ALIGN',d.time)
  elif phase=='ALIGN':
   fk.qpos[:]=d.qpos;fk.qpos[aq]=target[ids];mujoco.mj_forward(m,fk)
   poserr=np.linalg.norm(d.xpos[wrist]-fk.xpos[wrist]);rerr=np.linalg.norm(rot_error(fk.xmat[wrist].reshape(3,3),d.xmat[wrist].reshape(3,3)))
   aligned=aligned+.002 if poserr<.003 and rerr<.025 and np.max(abs(d.qvel[av]))<.08 else 0
   if aligned>=.1:change('CLOSE',d.time)
   elif elapsed>3:fail_reason='alignment timeout';break
  elif phase=='CLOSE':
   contact_dwell=contact_dwell+.002 if (forces>.1).sum()>=2 else 0
   if elapsed>=2 and (contact_dwell>=.2 or no_grip or pad_off):change('LIFT',d.time)
   elif elapsed>5:fail_reason='two-finger contact timeout';break
  elif phase=='LIFT' and elapsed>=phase_duration:
   change('HOLD',d.time);hold_start=d.time
  elif phase=='HOLD' and elapsed>=2:
   hold_end=d.time;change('RELEASE',d.time);release_start=d.time
  elif phase=='RELEASE' and elapsed>=1:change('SETTLE',d.time)
  elif phase=='SETTLE' and elapsed>=3:break
 else:fail_reason='90s horizon exhausted'
 r=np.asarray(rows);lift=r[:,3]-initcube[2];bodies=(r[:,7:10]>.01).sum(axis=1)
 hold=(r[:,0]>=(hold_start or 1e9)+.02)&(r[:,0]<=(hold_end or -1))
 h=r[hold];release=r[r[:,0]>=(release_start or 1e9)+2]
 minlift=float(np.min(lift[hold])) if len(h) else -1.
 slip=float(np.max(np.linalg.norm(h[:,4:7]-h[0,4:7],axis=1))) if len(h) else 1e9
 warnings=(np.array([w.number for w in d.warning])-warnings).tolist()
 gates=dict(completed=fail_reason is None,hold_7cm=len(h)>0 and minlift>=.07,
            two_fingers=len(h)>0 and int(np.min(bodies[hold]))>=2,
            no_support=len(h)>0 and float(np.max(h[:,10]))<.001,
            clearance_4cm=len(h)>0 and float(np.min(h[:,11]-.725))>=.04,
            slip_1cm=slip<.01,release_drop_6cm=len(release)>0 and len(h)>0 and h[-1,3]-np.min(release[:,3])>=.06,
            final_supported=r[-1,10]>.05,final_fingers_off=bodies[-1]==0,
            fixed_base=float(np.max(r[:,12]))<1e-12,no_external=peakext==0,no_warnings=not any(warnings))
 result=dict(runtime_stamp=st,success=all(bool(v) for v in gates.values()),gates={k:bool(v) for k,v in gates.items()},
             no_grip=no_grip,pad_off=pad_off,fail_reason=fail_reason,events=events,
             attribution=meta['method'],calibration_route=meta['geometric_route'],initial_condition=meta['initial_condition'],
             duration_s=float(d.time),steps=len(r),max_lift_m=float(np.max(lift)),hold_min_lift_m=minlift,
             hold_slip_m=slip,hold_min_contact_bodies=int(np.min(bodies[hold])) if len(h) else 0,
             hold_min_total_finger_normal_force_N=float(np.min(h[:,7:10].sum(axis=1))) if len(h) else 0.,
             hold_max_support_force_N=float(np.max(h[:,10])) if len(h) else 1e9,
             tracking_rms_rad=float(np.sqrt(np.mean(r[:,13:20]**2))),tracking_max_rad=maxtrack,
             torque_saturation_fraction=sat/(len(r)*7),warning_counts=warnings,wall_s=time.monotonic()-start,
             final_cube_xyz_m=r[-1,1:4].tolist(),scene=str(scene))
 np.savez_compressed(out/'trajectory.npz',qpos=frames,qvel=vels,right_arm_targets=armtargets,
                     phase=phases,time=r[::20,0],fps=25,scene=str(scene),runtime_stamp=json.dumps(st))
 with (out/'telemetry.csv').open('w') as f:
  f.write('# runtime_stamp='+json.dumps(st)+'\n');np.savetxt(f,r,delimiter=',')
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('plan',type=Path);p.add_argument('name');p.add_argument('--no-grip',action='store_true');p.add_argument('--pad-off',action='store_true');a=p.parse_args()
 simulate(a.root,a.plan,a.name,a.no_grip,a.pad_off)
