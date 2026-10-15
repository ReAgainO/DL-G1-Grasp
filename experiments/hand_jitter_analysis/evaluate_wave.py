"""Stamped jitter metrics, exact prefix checks, and unchanged grasp gates."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
import resource
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import datetime
import hashlib
import json
import sys
import numpy as np
import mujoco

R=Path(__file__).resolve().parent
B=Path('/home/group4/group4_dasc7606c')
OLD=Path('/data/group4/20261009-021611-codex-415484ce')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def detrend(values,times):
    X=np.c_[np.ones(len(times)),times-times[0]]
    return values-X@np.linalg.lstsq(X,values,rcond=None)[0]

def base_rotation(quat):
    w,x,y,z=quat.T
    return np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),
                     2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),
                     2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],axis=1).reshape(-1,3,3)

def measure(path):
    result=json.loads((path/'result.json').read_text())
    data=np.load(path/'dense_trace.npz',allow_pickle=False)
    assert json.loads(str(data['runtime_stamp_json']))==result['runtime_stamp']
    stamp=result['runtime_stamp']
    assert stamp['mujoco_version']==mujoco.__version__=='3.2.7'
    model=mujoco.MjModel.from_xml_path(str(path/'scene.xml'))
    assert model.neq==0 and model.nmocap==0
    assert result['no_cheats']['free_base'] and result['no_cheats']['free_object']
    assert result['no_cheats']['object_actuator_count']==0
    assert result['no_cheats']['xfrc_applied_max']==result['no_cheats']['qfrc_applied_max']==0
    for geom in ['right_thumb_fingertip','right_index_fingertip','right_middle_fingertip']:
        assert model.geom(geom).contype==0 and model.geom(geom).conaffinity==0
    joints=model.actuator_trnid[:,0]
    qa,va=model.jnt_qposadr[joints],model.jnt_dofadr[joints]
    times=data['time'];phases={}
    for phase,lo,hi in [('LATE_APPROACH',34,42),('CLOSE',42,45),('LIFT',46,50.5),('HOLD',50.5,53)]:
        use=(times>=lo)&(times<hi)
        t=times[use]
        if len(t)<10:
            phases[phase]={'samples':len(t)}
            continue
        q=data['qpos'][use];v=data['qvel'][use][:,va];ctrl=data['ctrl'][use]
        wrist=data['wrist_pos'][use]
        local=np.einsum('nji,nj->ni',base_rotation(q[:,3:7]),wrist-q[:,:3])
        values={'samples':len(t),'sample_dt_s':float(np.median(np.diff(t))),
                'wrist_detrended_rms_mm':float(1000*np.sqrt(np.mean(detrend(wrist,t)**2))),
                'wrist_rootlocal_detrended_rms_mm':float(1000*np.sqrt(np.mean(detrend(local,t)**2))),
                'root_detrended_rms_mm':float(1000*np.sqrt(np.mean(detrend(q[:,:3],t)**2))),
                'wrist_range_mm':(1000*np.ptp(wrist,axis=0)).tolist(),
                'cube_range_mm':(1000*np.ptp(data['cube_pos'][use],axis=0)).tolist(),
                'decoded_arm_step_rms_deg':float(np.rad2deg(np.sqrt(np.mean(np.diff(data['decoded_target'][use][:,22:29],axis=0)**2)))),
                'actuator_arm_step_rms_deg':float(np.rad2deg(np.sqrt(np.mean(np.diff(data['actuator_target'][use][:,22:29],axis=0)**2)))),
                'reference_arm_step_rms_deg':float(np.rad2deg(np.sqrt(np.mean(np.diff(data['body_reference'][use][:,22:29],axis=0)**2)))),
                'servo_offset_step_rms_deg':float(np.rad2deg(np.sqrt(np.mean(np.diff(data['servo_offset'][use],axis=0)**2)))),
                'thumb_load_min_N':float(data['thumb_load_N'][use].min()),
                'opposing_load_min_N':float(data['index_middle_load_N'][use].min())}
        for name,sl in [('arm',slice(22,29)),('finger',slice(36,43))]:
            residual=detrend(q[:,qa[sl]],t)
            freq=np.fft.rfftfreq(len(t),.005)
            power=np.abs(np.fft.rfft(residual,axis=0))**2
            band=(freq>=1)&(freq<=90)
            values[name+'_velocity_rms_rad_s']=float(np.sqrt(np.mean(v[:,sl]**2)))
            values[name+'_detrended_angle_rms_deg']=float(np.rad2deg(np.sqrt(np.mean(residual**2))))
            values[name+'_dominant_1_90Hz']=float(freq[band][np.argmax(power[band].sum(axis=1))])
            values[name+'_torque_step_rms_Nm']=float(np.sqrt(np.mean(np.diff(ctrl[:,sl],axis=0)**2)))
        phases[phase]=values
    return result,phases

wave=sys.argv[1]
design=json.loads((R/'configs'/(wave+'-design.json')).read_text())
assert (R/'configs'/(wave+'-done.json')).exists()
rows=[]
for config in design['trials']:
    episode=R/'out'/config['id'];source=OLD/'out'/config['source_episode']
    receipt=json.loads((R/'configs'/(config['id']+'-receipt.json')).read_text())
    if receipt['rc']!=0:
        rows.append({'id':config['id'],'classification':'infrastructure_error','receipt':receipt})
        continue
    result,metrics=measure(episode)
    old=json.loads((source/'result.json').read_text())
    assert result['runtime_stamp']['in_memory_geometry_sha']==old['runtime_stamp']['in_memory_geometry_sha']
    oldref=np.load(source/'reference.npz',allow_pickle=False)
    newref=np.load(episode/'reference.npz',allow_pickle=False)
    refmatches={key:np.array_equal(oldref[key],newref[key]) for key in ['body','hand','wrist']}
    assert all(refmatches.values())
    oldtrace=np.load(source/'trajectory.npz',allow_pickle=False)
    newtrace=np.load(episode/'trajectory.npz',allow_pickle=False)
    oldprefix=oldtrace['time']<config['start']
    newprefix=newtrace['time']<config['start']
    prefix={key:bool(np.array_equal(oldtrace[key][oldprefix],newtrace[key][newprefix]))
            for key in ['time','qpos','qvel','ctrl','decoded_target','body_reference','hand_reference','cube_pos','wrist_pos']}
    prefixmax={key:float(np.max(abs(oldtrace[key][oldprefix]-newtrace[key][newprefix]))) for key in prefix if key!='time'}
    exact_whole_baseline=None
    if config['tau']==0 and config['damping']==2 and config['servo_gain']==.1 and not config.get('no_grip'):
        exact_whole_baseline={key:bool(np.array_equal(oldtrace[key],newtrace[key])) for key in oldtrace.files if key!='runtime_stamp_json'}
    row={'id':config['id'],'config':config,'success':result['success'],'reason':result['reason'],
         'max_lift_mm':result['max_lift_m']*1000,'local_slip_mm':result['max_wristlocal_slip_alllift_m']*1000,
         'hold_safe_steps':result['hold_safe_steps'],'hold_support_steps':result['hold_support_steps'],
         'max_joint_overrun_rad':result['max_joint_limit_violation_rad'],
         'frozen_reference_arrays_identical':refmatches,'pretreatment_prefix_identical':prefix,'pretreatment_max_abs_delta':prefixmax,
         'whole_baseline_arrays_identical':exact_whole_baseline,'geometry_identity':True,'metrics':metrics,
         'source_result_sha':sha(episode/'result.json'),'source_dense_sha':sha(episode/'dense_trace.npz'),
         'runtime_stamp':result['runtime_stamp']}
    rows.append(row)
    print(json.dumps({key:row[key] for key in ['id','success','reason','max_lift_mm','local_slip_mm','pretreatment_prefix_identical','whole_baseline_arrays_identical']} | {'HOLD':metrics.get('HOLD')}),flush=True)
output={'wave':wave,'created':datetime.datetime.now().astimezone().isoformat(),'rows':rows,
        'runtime_stamp':{'mujoco_version':mujoco.__version__,'sys_executable':sys.executable,'python_version':sys.version,
                         'model_sha':{row['id']:row.get('runtime_stamp',{}).get('model_sha') for row in rows},
                         'scene_generator_sha':sha(R/'batch_plan.py'),'library_sha':sha(R/'lib/sonic_v11.py'),
                         'dt':.001,'metric_sample_dt_s':.005,'analysis_source_sha':sha(__file__)},
        'metric_convention':'position RMS is mean across sampled time and3 coordinate components after linear detrending; not vector-norm RMS or proof of sole causality',
        'scope':'MuJoCo3.2.7 current parameter family; contact monitoring does not establish hardware stability'}
path=R/'analysis'/(wave+'-evaluation.json')
with path.open('x') as f:
    json.dump(output,f,indent=2)
with (B/'logs'/R.name/'steps.md').open('a') as f:
    f.write('\n- '+output['created']+' Wave evaluation: '+str(path)+' SHA='+sha(path)+'; original v2 gate unchanged; exact prefix and reference arrays independently compared.\n')
