"""Stage3 constrained IK: explicit human-calibrated geometry, ARDY posture prior."""
import json,sys
from pathlib import Path
import mujoco,numpy as np
import trajectory as tr
import source_physics_core as core

def rot_error(target,current):
 qt=np.zeros(4);qc=np.zeros(4);qi=np.zeros(4);err=np.zeros(4)
 mujoco.mju_mat2Quat(qt,target.reshape(-1));mujoco.mju_mat2Quat(qc,current.reshape(-1))
 mujoco.mju_negQuat(qi,qc);mujoco.mju_mulQuat(err,qt,qi)
 if err[0]<0:err=-err
 v=err[1:];n=np.linalg.norm(v)
 return 2*v if n<1e-10 else v/n*(2*np.arctan2(n,err[0]))

def rotation_blend(A,B,u):
 qa=np.zeros(4);qb=np.zeros(4);mat=np.zeros(9)
 mujoco.mju_mat2Quat(qa,A.reshape(-1));mujoco.mju_mat2Quat(qb,B.reshape(-1))
 if qa@qb<0:qb=-qb
 angle=np.arccos(np.clip(qa@qb,-1,1))
 q=(1-u)*qa+u*qb if angle<1e-6 else (np.sin((1-u)*angle)*qa+np.sin(u*angle)*qb)/np.sin(angle)
 q/=np.linalg.norm(q);mujoco.mju_quat2Mat(mat,q);return mat.reshape(3,3)

def ik(m,d,aq,av,target,R,seed,prior,weight=.000001):
 q=seed.copy();jids=m.dof_jntid[av];lo=m.jnt_range[jids,0]+.001;hi=m.jnt_range[jids,1]-.001
 wrist=m.body('right_wrist_yaw_link').id; jp=np.zeros((3,m.nv));jr=jp.copy()
 for it in range(100):
  d.qpos[aq]=q;mujoco.mj_forward(m,d)
  ep=target-d.xpos[wrist];er=rot_error(R,d.xmat[wrist].reshape(3,3))
  if np.linalg.norm(ep)<.0001 and np.linalg.norm(er)<.0008:break
  mujoco.mj_jacBody(m,d,jp,jr,wrist)
  J=np.vstack([10*jp[:,av],jr[:,av],np.sqrt(weight)*np.eye(7)])
  e=np.r_[10*ep,er,np.sqrt(weight)*(prior-q)]
  dq=np.linalg.lstsq(J,e,rcond=None)[0];dq*=min(1,.12/max(np.max(abs(dq)),1e-12))
  q=np.clip(q+dq,lo,hi)
 d.qpos[aq]=q;mujoco.mj_forward(m,d)
 err=np.r_[target-d.xpos[wrist],rot_error(R,d.xmat[wrist].reshape(3,3))]
 return q,float(np.linalg.norm(err[:3])),float(np.linalg.norm(err[3:]))

def build(root,name='task_plan',prior_weight=.08):
 root=Path(root);out=root/'out'/name;out.mkdir()
 scene=core.prepare_model(root/'src/g1',out,[.267,-.118],.7745,True)
 m,d,ids,aq,av,qa,va,ix=tr.robot(scene);wrist=m.body('right_wrist_yaw_link').id
 cal=np.load(root/'src/manual_grasp_calibration.npz',allow_pickle=False)
 assert json.loads((root/'src/manual_grasp_calibration.json').read_text())['success']
 k=int(np.argmin(abs(cal['time']-12.0))) # Before closure: object is still upright on its support.
 assert len(cal['qpos'][k])==m.nq
 d.qpos[:]=cal['qpos'][k];mujoco.mj_forward(m,d)
 cal_offset=d.xpos[wrist]-d.body('red_cube').xpos;R=d.xmat[wrist].reshape(3,3).copy()
 grasp=np.array([.267,-.118,.7745])+cal_offset
 # The calibration is a geometry target, NOT a replayed joint trajectory.
 original=np.load(root/'out/repaired_guided_s42/reference.npz',allow_pickle=False)
 prior_frames=original['smoothed'];st=tr.stamp(scene)
 st['scene_generator_sha']=tr.sha(__file__)
 st['library_sha'].update(ardy_source_csv=tr.sha(root/'src/guided_s42.csv'),
                         processed_reference=tr.sha(root/'out/repaired_guided_s42/reference.npz'),
                         manual_grasp_calibration=tr.sha(root/'src/manual_grasp_calibration.npz'),task_plan_py=tr.sha(__file__))
 # Retain model-generated redundancy prior; task wrist pose constraints override it explicitly.
 high_k=int(np.argmin(abs(cal['time']-17.5)))
 d.qpos[:]=cal['qpos'][high_k];mujoco.mj_forward(m,d)
 pre=d.xpos[wrist].copy()+np.array([.267,-.118,.7745])-np.array([.267,-.118,.7745])
 high_R=d.xmat[wrist].reshape(3,3).copy()
 seed=prior_frames[300].copy()
 seeds=[seed,np.clip(core.DEFAULT[core.ARM],m.jnt_range[m.dof_jntid[av],0]+.03,m.jnt_range[m.dof_jntid[av],1]-.03),
        cal['qpos'][k][aq].copy(),cal['qpos'][high_k][aq].copy()]
 candidates=[ik(m,d,aq,av,pre,high_R,s,prior_frames[225]) for s in seeds]
 best=min(candidates,key=lambda r:10*r[1]+r[2]);q=best[0]
 if best[1]>.001 or best[2]>.01:raise RuntimeError(f'Pregrasp IK infeasible: {best[1:]}')
 qs=[];errors=[];poses=[];geo_q=[];prior_effect=[]
 # Two segments: pregrasp->grasp and grasp->vertical lift, 101 samples each.
 for phase in range(2):
  for j in range(101):
   x=j/100;u=x*x*x*(10+x*(-15+6*x))
   # A reachable geometric corridor from two HUMAN calibrated poses.
   # This is explicitly NOT an ARDY-generated end-effector route.
   low_q=cal['qpos'][k][aq];high_q=cal['qpos'][high_k][aq]
   qgeo=high_q*(1-u)+low_q*u if phase==0 else low_q*(1-u)+high_q*u
   d.qpos[aq]=qgeo;mujoco.mj_forward(m,d)
   pos=d.xpos[wrist].copy();orient=d.xmat[wrist].reshape(3,3).copy()
   frame=(225+75*u) if phase==0 else (300+125*u)
   fi=int(frame);f=frame-fi;prior=(1-f)*prior_frames[fi]+f*prior_frames[min(fi+1,len(prior_frames)-1)]
   jp=np.zeros((3,m.nv));jr=jp.copy();mujoco.mj_jacBody(m,d,jp,jr,wrist)
   J=np.vstack([10*jp[:,av],jr[:,av]])
   N=np.eye(7)-np.linalg.pinv(J)@J
   delta=prior_weight*N@(prior-qgeo)
   limits=m.jnt_range[m.dof_jntid[av]]
   alpha=min(1.,.03/max(np.max(abs(delta)),1e-10))
   for l in range(7):
    if delta[l]>1e-10:alpha=min(alpha,.8*(limits[l,1]-.002-qgeo[l])/delta[l])
    elif delta[l]<-1e-10:alpha=min(alpha,.8*(limits[l,0]+.002-qgeo[l])/delta[l])
   model_seed=qgeo+max(0,alpha)*delta
   q,ep,er=ik(m,d,aq,av,pos,orient,model_seed,prior,weight=0)
   qs.append(q.copy());errors.append([ep,er]);poses.append(pos);geo_q.append(qgeo.copy());prior_effect.append(q-qgeo)
 qs=np.array(qs);err=np.array(errors)
 # Phase timing is selected conservatively from smooth quintic velocity bounds.
 # Runtime follows these C2 trajectories but waits for alignment/contact events.
 down=qs[:101];up=qs[101:]
 def segment(q,duration=6):
  h=duration/100;coef=tr.coefficients(q,h);t=np.arange(0,duration+.001,.002)
  qq,v,a,j=tr.sample(coef,h,t)
  return qq,v,a,j
 downq,downv,downa,downj=segment(down);upq,upv,upa,upj=segment(up)
 ratio=max(1,float(max(np.max(abs(downv)),np.max(abs(upv)))/.6),
           float(np.sqrt(max(np.max(abs(downa)),np.max(abs(upa)))/1.5)),
           float(np.cbrt(max(np.max(abs(downj)),np.max(abs(upj)))/12)))*1.01
 phase_duration=6*ratio
 if phase_duration>18:raise RuntimeError(f'Phase duration bound18s exceeded: {phase_duration}')
 downq,downv,downa,downj=segment(down,phase_duration);upq,upv,upa,upj=segment(up,phase_duration)
 velocities=float(max(np.max(abs(downv)),np.max(abs(upv))))
 acceleration=float(max(np.max(abs(downa)),np.max(abs(upa))))
 jerk=float(max(np.max(abs(downj)),np.max(abs(upj))))
 lo=m.jnt_range[m.dof_jntid[av],0];hi=m.jnt_range[m.dof_jntid[av],1]
 boundary=float(np.max(abs(downq[-1]-upq[0])))
 gates=dict(segment_boundary_continuous=boundary<1e-8,ik_position=bool(np.max(err[:,0])<.001),ik_rotation=bool(np.max(err[:,1])<.01),
            within_limits=bool((qs>=lo).all() and (qs<=hi).all()),velocity=velocities<.6,acceleration=acceleration<1.5,jerk=jerk<12)
 meta=dict(runtime_stamp=st,success=all(gates.values()),gates=gates,
           method=('hybrid geometric wrist constraints + bounded IK with ARDY posture prior; not native ARDY grasp' if prior_weight else 'human calibrated geometric route only; ZERO ARDY posture influence'),
           geometric_route='human calibrated pregrasp/grasp endpoint joint interpolation converted to Cartesian corridor; ARDY only perturbs redundant posture',
           ardy_nullspace_weight=prior_weight,ardy_prior_target_effect_rms_rad=float(np.sqrt(np.mean(np.array(prior_effect)**2))),
           phase_duration_s=phase_duration,
           segment_boundary_max_jump_rad=boundary,
           calibration_frame_time=float(cal['time'][k]),calibration_wrist_cube_offset_m=cal_offset.tolist(),
           pregrasp_calibration_time=float(cal['time'][high_k]),pregrasp_position_m=pre.tolist(),
           max_ik_position_error_m=float(np.max(err[:,0])),max_ik_rotation_error_rad=float(np.max(err[:,1])),
           velocity_max_rad_s=velocities,accel_max_rad_s2=acceleration,jerk_max_rad_s3=jerk,
           ardy_prior_ik_mean_deviation_rad=float(np.sqrt(np.mean((qs[:101]-prior_frames[np.linspace(225,300,101).astype(int)])**2))),
           initial_condition='pregrasp IK pose; arm initialized above cube, NOT full neutral-to-object approach')
 np.savez_compressed(out/'plan.npz',down_q=downq,down_v=downv,down_a=downa,up_q=upq,up_v=upv,up_a=upa,
                     R=R,grasp_position=grasp,waypoint_q=qs,waypoint_ee=np.asarray(poses),runtime_stamp=json.dumps(st),metadata=json.dumps(meta))
 (out/'result.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
 if not meta['success']:raise RuntimeError('Task plan gates failed; do not run contact grasp')

if __name__=='__main__':build(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else 'task_plan',float(sys.argv[3]) if len(sys.argv)>3 else .08)
