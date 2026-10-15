"""Stage 2: contact-free, bounded physical tracking of repaired ARDY references."""
import argparse,json,time
from pathlib import Path
import mujoco
import numpy as np
import trajectory as tr
import source_physics_core as core

def full_mass(m,d):
 M=np.empty((m.nv,m.nv))
 if tuple(map(int,mujoco.__version__.split('.')[:2]))>=(3,14): mujoco.mj_fullM(m,d,M)
 else: mujoco.mj_fullM(m,M,d.qM)
 return M

def command(m,d,qa,va,ix,arm_ids,arm_va,q,v,a,mode):
 kp,kd=core.gains(); kp=kp[ix];kd=kd[ix]
 if mode!='legacy':
  kp[arm_ids]=[100,100,80,80,35,35,35]
  kd[arm_ids]=[8,8,6,6,2.5,2.5,2.5]
 tau=kp*(q-d.qpos[qa])-kd*d.qvel[va]
 if mode!='legacy':
  tau+=kd*v
  # Compensate arm dynamics only; finger physical grasp gains remain unchanged.
  acc=np.zeros(m.nv);acc[arm_va]=a[arm_ids]
  ff=d.qfrc_bias+full_mass(m,d)@acc
  tau[arm_ids]+=ff[arm_va]
 clipped=np.clip(tau,m.actuator_ctrlrange[:,0],m.actuator_ctrlrange[:,1])
 return clipped,tau

def tracking(root,reference,out,mode):
 start=time.monotonic();root=Path(root);out=Path(out);out.mkdir()
 scene=core.prepare_model(root/'src/g1',out,[.267,-.118],.7745,True)
 m,d,ids,aq,av,qa,va,ix=tr.robot(scene)
 # Diagnostic isolation: disable ALL robot collision geoms. Cube/support remain physical.
 arm_bodies=[]
 for i in range(m.nbody):
  n=m.body(i).name or ''
  if n.startswith(('right_shoulder','right_elbow','right_wrist','right_hand')):arm_bodies.append(i)
 for g in range(m.ngeom):
  if m.geom_bodyid[g]!=m.body('red_cube').id and m.geom_bodyid[g]!=0:
   m.geom_contype[g]=0;m.geom_conaffinity[g]=0
 st=tr.stamp(scene);st['scene_generator_sha']=tr.sha(__file__)
 st['library_sha'].update(reference_npz=tr.sha(reference),control_py=tr.sha(__file__),source_core=tr.sha(core.__file__))
 st['diagnostic_collision_override']='all robot geoms disabled after XML load; not a grasp scene'
 z=np.load(reference,allow_pickle=False);rq,rv,ra=z['q'],z['v'],z['a'];times=z['time']
 if len(times)>45001:raise ValueError('reference exceeds bounded90s')
 d.qpos[aq]=rq[0];mujoco.mj_forward(m,d)
 target=d.qpos[qa].copy();v=np.zeros(m.nu);a=np.zeros(m.nu)
 samples=[];frames=[];vels=[];targets=[];sat=0;max_actual=.0; warnings=np.array([w.number for w in d.warning])
 base=d.body('pelvis').xpos.copy()
 wrist=m.body('right_wrist_yaw_link').id; fk=mujoco.MjData(m)
 for k in range(len(times)):
  target[ids]=rq[k];v[ids]=rv[k];a[ids]=ra[k]
  ctrl,tau=command(m,d,qa,va,ix,ids,av,target,v,a,mode)
  sat+=int(np.count_nonzero(abs(ctrl[ids]-tau[ids])>1e-10));d.ctrl[:]=ctrl
  mujoco.mj_step(m,d)
  if not np.isfinite(d.qpos).all():raise RuntimeError('Nonfinite state')
  err=d.qpos[aq]-rq[k];max_actual=max(max_actual,float(np.max(abs(d.qvel[av]))))
  if k%20==0:
   fk.qpos[:]=d.qpos;fk.qpos[aq]=rq[k];mujoco.mj_forward(m,fk)
   ee=float(np.linalg.norm(d.xpos[wrist]-fk.xpos[wrist]))
   samples.append([d.time,*err,ee,*d.ctrl[ids],*d.qvel[av]])
   frames.append(d.qpos.copy());vels.append(d.qvel.copy());targets.append(rq[k].copy())
 r=np.asarray(samples); window=r[r[:,0]>.5]
 warning_delta=(np.array([w.number for w in d.warning])-warnings).tolist()
 rms=float(np.sqrt(np.mean(window[:,1:8]**2)));maxerr=float(np.max(abs(window[:,1:8])))
 ee=float(np.max(window[:,8]));baseerr=float(np.linalg.norm(d.body('pelvis').xpos-base))
 gates=dict(rms_under_005rad=rms<.05,max_under_015rad=maxerr<.15,wrist_error_under_01m=ee<.01,
            torque_saturation_under_1pct=sat/(len(times)*7)<.01,no_warnings=not any(warning_delta),fixed_base=baseerr<1e-12)
 result=dict(runtime_stamp=st,success=all(gates.values()),gates=gates,controller=mode,
             diagnostic='contact-free tracking only; NO physical grasp claim',duration_s=float(d.time),steps=len(times),
             tracking_rms_rad=rms,tracking_max_rad=maxerr,wrist_tracking_max_m=ee,
             torque_saturation_fraction=sat/(len(times)*7),actual_speed_max_rad_s=max_actual,
             warning_counts=warning_delta,wall_s=time.monotonic()-start)
 np.savez_compressed(out/'trajectory.npz',qpos=frames,qvel=vels,right_arm_targets=targets,time=r[:,0],
                     runtime_stamp=json.dumps(st),reference=str(reference))
 with (out/'tracking.csv').open('w') as f:
  f.write('# runtime_stamp='+json.dumps(st)+'\n');np.savetxt(f,r,delimiter=',')
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('reference',type=Path);p.add_argument('name');p.add_argument('--mode',choices=['legacy','feedforward'],default='feedforward');a=p.parse_args()
 tracking(a.root,a.reference,a.root/'out'/a.name,a.mode)
