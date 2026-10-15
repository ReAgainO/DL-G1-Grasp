"""Bounded free-base SONIC stand/moving-arm integration probe, not a grasp."""
import argparse,json,time
from pathlib import Path
import mujoco,numpy as np
import source_physics_core as core
import sonic_v11 as sonic

def run(name,duration=6,dynamic=False,reference_off=False):
 root=Path(__file__).resolve().parent;out=root/'out'/name;out.mkdir()
 scene=root/'src/g1/scene_grasp_hand.xml'
 m=mujoco.MjModel.from_xml_path(str(scene));d=mujoco.MjData(m)
 assert m.opt.timestep==.002 and m.neq==0
 controller=sonic.SonicV11(m)
 d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0]
 d.qpos[controller.aq]=sonic.DEFAULT_ANGLES
 names=[a.get('name') for a in core.ET.parse(root/'src/g1/g1_29dof_with_hand.xml').find('actuator')]
 hand=np.array([m.actuator(names[i]).id for i in core.HAND]);hj=m.actuator_trnid[hand,0];hq=m.jnt_qposadr[hj];hv=m.jnt_dofadr[hj]
 d.qpos[hq]=core.OPEN;mujoco.mj_forward(m,d)
 initial=d.qpos[:3].copy();start=time.monotonic();rows=[];frames=[];vels=[];ref_frames=[];warnings=np.array([x.number for x in d.warning]);fail=None
 def reference(times):
  q=np.tile(sonic.DEFAULT_ANGLES,(len(times),1));v=np.zeros_like(q)
  if dynamic:
   # Smooth scripted identification input, deliberately NOT labelled ARDY.
   q[:,22]+=.15*np.sin(2*np.pi*times/6);v[:,22]=.15*(2*np.pi/6)*np.cos(2*np.pi*times/6)
  return q,v,np.tile([1.,0.,0.,0.],(len(times),1))
 for step in range(int(duration/.002)):
  t=step*.002
  if step%10==0:
   times=t+np.arange(10)*.1;q,v,r=reference(times)
   if reference_off:q=np.tile(sonic.DEFAULT_ANGLES,(10,1));v*=0
   controller.step_policy(d,q,v,r)
  d.ctrl[:29]=controller.torques(d)
  ht=core.gains()[0][core.HAND]*(core.OPEN-d.qpos[hq])-core.gains()[1][core.HAND]*d.qvel[hv]
  d.ctrl[hand]=np.clip(ht,m.actuator_ctrlrange[hand,0],m.actuator_ctrlrange[hand,1])
  assert np.max(abs(d.xfrc_applied))==np.max(abs(d.qfrc_applied))==0
  mujoco.mj_step(m,d)
  ref,_,_=reference(np.array([d.time]));rot=sonic.rotation(d.qpos[3:7]);err=d.qpos[controller.aq]-ref[0]
  rows.append([d.time,*d.qpos[:3],rot[2,2],np.linalg.norm(d.qpos[:2]-initial[:2]),*err])
  if step%20==0:frames.append(d.qpos.copy());vels.append(d.qvel.copy());ref_frames.append(ref[0].copy())
  if not np.isfinite(d.qpos).all() or d.qpos[2]<.55 or rot[2,2]<.65:
   fail='fall/nonfinite';break
 r=np.asarray(rows);warn=np.array([x.number for x in d.warning])-warnings
 stamp=dict(mujoco_version=mujoco.__version__,sys_executable=__import__('sys').executable,python_version=__import__('sys').version,
            model_sha={'scene':sonic.sha(scene),'robot':sonic.sha(root/'src/g1/g1_29dof_with_hand.xml')},
            scene_generator_sha=sonic.sha(__file__),library_sha={'sonic_v11':sonic.sha(sonic.__file__),**controller.model_stamp},dt=.002)
 result=dict(runtime_stamp=stamp,success=bool(fail is None and not warn.any() and r[:,4].min()>.9 and r[:,5].max()<.1),
             kind='SONIC free-base integration/identification probe; NOT a grasp and NOT ARDY',dynamic=dynamic,reference_off=reference_off,
             fail_reason=fail,duration_s=d.time,min_base_z_m=float(r[:,3].min()),min_up_z=float(r[:,4].min()),
             max_drift_m=float(r[:,5].max()),body_tracking_rms_rad=float(np.sqrt(np.mean(r[:,6:]**2))),
             right_arm_tracking_rms_rad=float(np.sqrt(np.mean(r[:,6+22:6+29]**2))),
             max_target_from_default_rad=float(np.max(abs(controller.target-sonic.DEFAULT_ANGLES))),
             warnings=warn.tolist(),wall_s=time.monotonic()-start,sonic=controller.audit())
 np.savez_compressed(out/'trajectory.npz',qpos=frames,qvel=vels,body_reference=ref_frames,time=r[::20,0],fps=25,
                     scene=str(scene),runtime_stamp=json.dumps(stamp))
 with (out/'telemetry.csv').open('w') as f:
  f.write('# runtime_stamp='+json.dumps(stamp)+'\n');np.savetxt(f,r,delimiter=',')
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 if fail:raise RuntimeError(fail)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--duration',type=float,default=6);p.add_argument('--dynamic',action='store_true');p.add_argument('--reference-off',action='store_true');a=p.parse_args()
 assert 0<a.duration<=12
 run(a.name,a.duration,a.dynamic,a.reference_off)
