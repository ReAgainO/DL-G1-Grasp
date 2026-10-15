"""Zero-integration FK and motor/reference attribution of a completed episode."""
import argparse,gzip,hashlib,json,sys
from pathlib import Path
import numpy as np,mujoco

p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args()
root=Path(__file__).resolve().parent;out=root/'out'/a.name;dest=out/'control-analysis.json';assert not dest.exists()
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
r=json.loads((out/'result.json').read_text());z=np.load(out/'trajectory.npz',allow_pickle=False)
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
m=mujoco.MjModel.from_xml_path(str(out/'scene.xml'));d=mujoco.MjData(m)
j=m.actuator_trnid[:29,0];aq=m.jnt_qposadr[j];av=m.jnt_dofadr[j];wrist=m.body('right_wrist_yaw_link').id
assert len(z['time'])==len(z['qpos'])<=2250
positions=[]
for q,v in zip(z['qpos'],z['qvel']):
    d.qpos[:]=q;d.qvel[:]=v;mujoco.mj_forward(m,d);positions.append(d.xpos[wrist].copy())
positions=np.asarray(positions);arm=z['qpos'][:,aq[22:29]];decoded=z['decoded_motor_target'][:,22:29];virtual=z['body_reference'][:,22:29]
e=arm-decoded;ev=arm-virtual
records=[];lo=m.jnt_range[j[22:29],0];hi=m.jnt_range[j[22:29],1]
for phase in dict.fromkeys(z['phase']):
    mask=z['phase']==phase;n=int(mask.sum());assert n>0
    targets=z['wrist_target'][mask];valid=np.isfinite(targets).all(axis=1);delta=positions[mask][valid]-targets[valid]
    rr=dict(phase=str(phase),sample_count=n,motor_error_rms_rad=float(np.sqrt(np.mean(e[mask]**2))),motor_error_per_joint_rms_rad=np.sqrt(np.mean(e[mask]**2,axis=0)).tolist(),motor_error_mean_rad=e[mask].mean(axis=0).tolist(),virtual_error_rms_rad=float(np.sqrt(np.mean(ev[mask]**2))),actual_velocity_per_joint_max_rad_s=np.abs(z['qvel'][mask][:,av[22:29]]).max(axis=0).tolist(),joint_limits_exceeded_sample_count=int(((arm[mask]<lo-1e-3)|(arm[mask]>hi+1e-3)).any(axis=1).sum()))
    if len(delta):rr.update(wrist_position_error_rms_m=float(np.sqrt(np.mean(np.sum(delta**2,axis=1)))),wrist_vertical_error_min_m=float(delta[:,2].min()),wrist_vertical_error_max_m=float(delta[:,2].max()),wrist_vertical_error_mean_m=float(delta[:,2].mean()))
    records.append(rr)
mask=(z['phase']=='LIFT')|(z['phase']=='HOLD');samples=[]
if mask.any():
    first=float(z['time'][mask][0])
    for dt in np.arange(0,10,.5):
        k=int(np.argmin(abs(z['time']-(first+dt))))
        if not mask[k]:continue
        samples.append(dict(time_s=float(z['time'][k]),phase=str(z['phase'][k]),wrist_xyz_m=positions[k].tolist(),wrist_target_xyz_m=z['wrist_target'][k].tolist(),motor_error_rad=e[k].tolist(),virtual_error_rad=ev[k].tolist()))
answer=dict(runtime_stamp={**r['runtime_stamp'],'sys_executable':sys.executable,'python_version':sys.version,'scene_generator_sha':sha(__file__)},source_episode_sha=sha(out/'result.json'),physical_steps=0,position_timing='postintegration FK from saved qpos; targets saved from preceding control update',sample_hz=25,aliasing_warning='25Hz motor target samples cannot certify 50Hz decoder jerk or 500Hz torque peaks',joint_names=[m.joint(int(v)).name for v in j[22:29]],phases=records,lift_samples=samples)
dest.write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(dict(physical_steps=0,phases=records),indent=2))
