"""Original ARDY NPZ -> official SONIC29 body actions in physical free-base G1.

This entry is a tracking/reaching stage, NOT a grasp claim. Hands stay open.
Upper-only projection, explicit startup ramp and speed are recorded modifications.
"""
import argparse,json,time
from pathlib import Path
import numpy as np,mujoco
import source_physics_core as core
import sonic_v11 as sonic
from motion_input import ArdyMotion

def run(stem,name,speed=.5,upper_only=True,reference_off=False):
 root=Path(__file__).resolve().parent;out=root/'out'/name;out.mkdir()
 path=root/'src/original_motions'/stem
 motion=ArdyMotion(path.with_suffix('.npz'),check_csv=path.with_suffix('.csv'))
 scene=root/'src/g1/scene_grasp_hand.xml'
 m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m);controller=sonic.SonicV11(m)
 expected=[m.joint(int(j)).name for j in controller.jids]
 assert expected==motion.joint_names,'Joint-name order mismatch'
 limits=m.jnt_range[controller.jids];raw=motion.qpos[:,7:]
 violations=((raw<limits[:,0]-.00001)|(raw>limits[:,1]+.00001)).sum()
 if violations:raise ValueError('Raw NPZ joint limit violations '+str(violations)+'; explicit repair required')
 if not .25<=speed<=1:raise ValueError('Speed bound.25..1')
 d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[controller.aq]=sonic.DEFAULT_ANGLES
 hands=np.arange(36,43);hj=m.actuator_trnid[hands,0];hq=m.jnt_qposadr[hj];hv=m.jnt_dofadr[hj]
 d.qpos[hq]=core.OPEN;mujoco.mj_forward(m,d)
 cube=m.body('red_cube').id;wrist=m.body('right_wrist_yaw_link').id;fk=mujoco.MjData(m)
 start=time.monotonic();initial=d.qpos[:3].copy();cubeinitial=d.xpos[cube].copy();rows=[];frames=[];vels=[];refs=[];phases=[]
 warn0=np.array([x.number for x in d.warning]);fail=None;duration=min(24,4+motion.times[-1]/speed+2)
 def reference(times):
  q,v,r=motion.sample(np.maximum(0,times-4)*speed);v*=speed
  # Follow generated RIGHT ARM; fix lowerbody/waist/left-arm reference, not actual robot state.
  if upper_only:
   selected=q[:,22:29].copy();selectedv=v[:,22:29].copy()
   q[:]=sonic.DEFAULT_ANGLES;v[:]=0;q[:,22:29]=selected;v[:,22:29]=selectedv;r[:]=[1,0,0,0]
  for i,t in enumerate(times):
   if t<2:q[i]=sonic.DEFAULT_ANGLES;v[i]=0;r[i]=[1,0,0,0]
   elif t<4:
    x=(t-2)/2;u=x**3*(10-15*x+6*x*x);du=30*x*x*(1-x)**2/2
    delta=q[i]-sonic.DEFAULT_ANGLES;q[i]=sonic.DEFAULT_ANGLES+u*delta;v[i]=du*delta
    # Root rotation ramp is intentionally identity in projected upper-only mode.
    if not upper_only:
     z=(1-u)*np.array([1.,0,0,0])+u*r[i];r[i]=z/np.linalg.norm(z)
  return q,v,r
 externalmax=0.;right_hand_contact_ticks=0;nonhand_cube_ticks=0
 for step in range(int(duration/.002)):
  t=step*.002;phase='SETTLE' if t<2 else 'RAMP' if t<4 else 'ARDY' if t<4+motion.times[-1]/speed else 'HOLD_FINAL'
  if step%10==0:
   q,v,r=reference(t+np.arange(10)*.1)
   if reference_off:q[:]=sonic.DEFAULT_ANGLES;v[:]=0;r[:]=[1,0,0,0]
   controller.step_policy(d,q,v,r)
  d.ctrl[:29]=controller.torques(d)
  kp,kd=core.gains();ht=kp[core.HAND]*(core.OPEN-d.qpos[hq])-kd[core.HAND]*d.qvel[hv]
  d.ctrl[hands]=np.clip(ht,m.actuator_ctrlrange[hands,0],m.actuator_ctrlrange[hands,1])
  externalmax=max(externalmax,float(np.max(abs(d.qfrc_applied))),float(np.max(abs(d.xfrc_applied))))
  mujoco.mj_step(m,d)
  ref,_,_=reference(np.array([d.time]));error=d.qpos[controller.aq]-ref[0]
  fk.qpos[:]=d.qpos;fk.qpos[controller.aq]=ref[0];mujoco.mj_forward(m,fk)
  wrist_error=np.linalg.norm(d.xpos[wrist]-fk.xpos[wrist]);gap=np.linalg.norm(d.xpos[wrist]-d.xpos[cube])
  cubecontact=m.geom('red_cube_geom').id;right=False;other=False
  for k in range(d.ncon):
   con=d.contact[k]
   if cubecontact not in (con.geom1,con.geom2):continue
   g=con.geom2 if con.geom1==cubecontact else con.geom1;b=m.geom_bodyid[g]
   n=m.body(b).name or ''
   if n.startswith('right_hand_'):right=True
   elif b!=0:other=True
  right_hand_contact_ticks+=int(right);nonhand_cube_ticks+=int(other)
  rot=sonic.rotation(d.qpos[3:7]);rows.append([d.time,*d.qpos[:3],rot[2,2],np.linalg.norm(d.qpos[:2]-initial[:2]),
                                           wrist_error,gap,d.xpos[cube,2]-cubeinitial[2],*error])
  if step%20==0:frames.append(d.qpos.copy());vels.append(d.qvel.copy());refs.append(ref[0]);phases.append(phase)
  if not np.isfinite(d.qpos).all() or d.qpos[2]<.55 or rot[2,2]<.65:fail='fall/nonfinite';break
 rows=np.asarray(rows);active=rows[:,0]>=4
 assert active.any(),'No generated motion consumed'
 warnings=np.array([x.number for x in d.warning])-warn0
 stamp=dict(mujoco_version=mujoco.__version__,sys_executable=__import__('sys').executable,python_version=__import__('sys').version,
            model_sha={'scene':sonic.sha(scene),'robot':sonic.sha(root/'src/g1/g1_29dof_with_hand.xml')},scene_generator_sha=sonic.sha(__file__),
            library_sha={**controller.model_stamp,'sonic_v11':sonic.sha(sonic.__file__),'motion_input':sonic.sha(root/'motion_input.py'),
                         'source_npz':motion.audit['source_npz_sha256'],'converter_asset':motion.audit['converter_asset_sha'],
                         'action_adapter':sonic.sha(root/'official_refs/sonic_action_adapter.py')},dt=.002)
 result=dict(runtime_stamp=stamp,tracking_stage_pass=bool(fail is None and not warnings.any() and rows[:,4].min()>.9 and
              np.sqrt(np.mean(rows[active,9+22:9+29]**2))<.1),physical_grasp_established=False,
             kind='original ARDY NPZ -> SONIC physical reaching/tracking; fingers open',source=motion.audit,
             input_processing=dict(upper_only_projection=upper_only,speed=speed,neutral_settle_s=2,startup_ramp_s=2,
                                   raw_joint_limit_violations=int(violations),arm_ik_or_direct_override=False,reference_off=reference_off,
                                   root_translation='not in SONIC v1.1 G1-mode input; not used as kinematic body teleport'),
             fail_reason=fail,duration_s=d.time,min_up_z=float(rows[:,4].min()),max_drift_m=float(rows[:,5].max()),
             right_arm_tracking_rms_rad=float(np.sqrt(np.mean(rows[active,9+22:9+29]**2))),
             wrist_local_fk_tracking_max_m=float(rows[active,6].max()),wrist_to_cube_min_m=float(rows[active,7].min()),
             wrist_to_cube_final_m=float(rows[-1,7]),cube_peak_lift_m=float(rows[:,8].max()),
             right_hand_cube_contact_ticks=right_hand_contact_ticks,nonhand_cube_contact_ticks=nonhand_cube_ticks,
             peak_external_force=externalmax,warnings=warnings.tolist(),wall_s=time.monotonic()-start,sonic=controller.audit())
 np.savez_compressed(out/'trajectory.npz',qpos=frames,qvel=vels,body_reference=refs,phase=phases,time=rows[::20,0],fps=25,scene=str(scene),runtime_stamp=json.dumps(stamp))
 with (out/'telemetry.csv').open('w') as f:f.write('# runtime_stamp='+json.dumps(stamp)+'\n');np.savetxt(f,rows,delimiter=',')
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['source','sonic','runtime_stamp']},indent=2))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stem',choices=['near_s42','control_s42','far_s42']);p.add_argument('name');p.add_argument('--speed',type=float,default=.5)
 p.add_argument('--full-body',action='store_true');p.add_argument('--reference-off',action='store_true');a=p.parse_args()
 run(a.stem,a.name,a.speed,not a.full_body,a.reference_off)
