"""Bounded, explicit ARDY postprocessing; no claim of unmodified model output."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import mujoco
import source_physics_core as core

NAMES=['right_shoulder_pitch','right_shoulder_roll','right_shoulder_yaw','right_elbow',
       'right_wrist_roll','right_wrist_pitch','right_wrist_yaw']

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def stamp(mpath):
 p=Path(mpath)
 return dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
             model_sha={'scene':sha(p),'robot':sha(p.parent/'g1_fixed_base.xml')},
             scene_generator_sha=sha(core.__file__),library_sha={'trajectory_py':sha(__file__)},dt=.002,timestep=.002)

def robot(scene):
 m=mujoco.MjModel.from_xml_path(str(scene)); d=mujoco.MjData(m)
 ids=np.array([m.actuator(n).id for n in NAMES]); j=m.actuator_trnid[ids,0]
 allj=m.actuator_trnid[:,0]; qa=m.jnt_qposadr[allj]; va=m.jnt_dofadr[allj]
 # Preserve original name mapping after removing waist joints.
 original=[a.get('name') for a in core.ET.parse(Path(scene).parent.parent/'src/g1/g1_29dof_with_hand.xml').find('actuator')]
 ix=np.array([original.index(m.actuator(i).name) for i in range(m.nu)])
 default=np.r_[core.DEFAULT,np.zeros(14)]; default[core.HAND]=core.OPEN
 d.qpos[qa]=np.clip(default[ix],m.jnt_range[allj,0],m.jnt_range[allj,1])
 mujoco.mj_forward(m,d)
 return m,d,ids,m.jnt_qposadr[j],m.jnt_dofadr[j],qa,va,ix

def smooth(q,sigma=20):
 radius=min(100,int(4*sigma)); x=np.arange(-radius,radius+1)
 k=np.exp(-.5*(x/sigma)**2); k/=k.sum()
 p=np.pad(q,((radius,radius),(0,0)),mode='reflect')
 return np.column_stack([np.convolve(p[:,j],k,'valid') for j in range(q.shape[1])])

def coefficients(q,h):
 v=np.gradient(q,h,axis=0); a=np.gradient(v,h,axis=0)
 v[0]=v[-1]=0; a[0]=a[-1]=0
 delta=q[1:]-q[:-1]; v0=v[:-1]*h; v1=v[1:]*h; a0=a[:-1]*h*h; a1=a[1:]*h*h
 return np.stack([q[:-1],v0,.5*a0,10*delta-6*v0-4*v1-1.5*a0+.5*a1,
                  -15*delta+8*v0+7*v1+1.5*a0-a1,6*delta-3*v0-3*v1-.5*a0+.5*a1],axis=1)

def sample(coeff,h,t):
 x=np.clip(t/h,0,len(coeff)-1e-10); idx=np.minimum(x.astype(int),len(coeff)-1); u=x-idx
 c=coeff[idx]
 q=sum(c[:,i]*u[:,None]**i for i in range(6))
 v=sum(i*c[:,i]*u[:,None]**(i-1) for i in range(1,6))/h
 a=sum(i*(i-1)*c[:,i]*u[:,None]**(i-2) for i in range(2,6))/h**2
 jerk=sum(i*(i-1)*(i-2)*c[:,i]*u[:,None]**(i-3) for i in range(3,6))/h**3
 return q,v,a,jerk

def repair(source,scene,out,sigma=20):
 m,d,ids,aq,av,qa,va,ix=robot(scene)
 raw=np.loadtxt(source,delimiter=',')[:,29:36]
 lo=m.jnt_range[m.actuator_trnid[ids,0],0]+.03; hi=m.jnt_range[m.actuator_trnid[ids,0],1]-.03
 # Every joint range is <2pi: no legal alternate branch for an out-of-range angle.
 # Do NOT naively unwrap into impossible hinge configurations.
 limited=np.clip(raw,lo,hi)
 q=smooth(limited,sigma)
 coef=coefficients(q,.04)
 fine=np.arange(0,(len(q)-1)*.04+.001,.002)
 _,v,a,j=sample(coef,.04,fine)
 scale=max(1,float(np.max(abs(v))/.6),float(np.sqrt(np.max(abs(a))/1.5)),
           float(np.cbrt(np.max(abs(j))/12))) *1.01
 duration=(len(q)-1)*.04*scale
 if duration>88: raise ValueError(f'Required duration {duration:.3f}s exceeds 88s experiment bound')
 t=np.arange(0,duration+.001,.002); qq,vv,aa,jj=sample(coef,.04,t/scale)
 vv/=scale;aa/=scale**2;jj/=scale**3
 gates=dict(finite=bool(np.isfinite(qq).all()),joint_range=bool((qq>=lo-1e-6).all() and (qq<=hi+1e-6).all()),
            velocity=bool(np.max(abs(vv))<=.601),acceleration=bool(np.max(abs(aa))<=1.501),jerk=bool(np.max(abs(jj))<=12.01))
 st=stamp(scene); st['library_sha']['source_csv']=sha(source)
 out=Path(out);out.mkdir()
 meta=dict(runtime_stamp=st,gates=gates,success=all(gates.values()),source=str(source),source_frames=len(raw),
           generated_source='ARDY; source qpos projected to fixed pelvis/waist right arm',
           processing='joint-limit projection + positive Gaussian smoothing + C2 quintic interpolation + global time scaling',
           angular_branch_policy='all hinge ranges <2pi; reject naive unwrap; infeasible endpoints projected explicitly',
           sigma_frames=sigma,duration_s=duration,time_scale=scale,
           raw_max_delta_rad=float(np.max(abs(np.diff(raw,axis=0)))),
           raw_out_of_range_cells=int(((raw<lo)|(raw>hi)).sum()),raw_repair_rms_rad=float(np.sqrt(np.mean((q-raw)**2))),
           velocity_max_rad_s=float(np.max(abs(vv))),accel_max_rad_s2=float(np.max(abs(aa))),jerk_max_rad_s3=float(np.max(abs(jj))))
 np.savez_compressed(out/'reference.npz',time=t,q=qq,v=vv,a=aa,j=jj,
                     raw=raw,limited=limited,smoothed=q,runtime_stamp=json.dumps(st),metadata=json.dumps(meta))
 (out/'result.json').write_text(json.dumps(meta,indent=2)+'\n'); print(json.dumps(meta,indent=2))
 if not meta['success']: raise RuntimeError('Stage1 kinematic gates failed')
 return meta

if __name__=='__main__':
 d=Path(sys.argv[1]); stage=d/'model';stage.mkdir(exist_ok=True)
 if not (stage/'scene_fixed_grasp.xml').exists(): core.prepare_model(d/'src/g1',stage,[.267,-.118],.7745,True)
 for name in ['guided_s42','guided_cfg8_s42']:
  repair(d/'src'/f'{name}.csv',stage/'scene_fixed_grasp.xml',d/'out'/f'repaired_{name}')
