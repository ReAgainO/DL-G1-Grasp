"""Read-only post-run audit of the frozen native-hand positive and controls.

FK here uses saved post-step qpos, whereas in-loop xpos/forces were observed
at mj_step's evaluation stage. Sampled FK slip is diagnostic, not replacement
for the original 1 ms runtime success gate.
"""
import os,resource
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import json,hashlib,datetime
import numpy as np,mujoco

D=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
positive=D/'out/side80_native3'
negative=D/'out/side80_native_negative3'
repeat=D/'out/side80_native3_repeat'
result=json.loads((positive/'result.json').read_text())
assert result['runtime_stamp']['mujoco_version']==mujoco.__version__=='3.2.7'
model=mujoco.MjModel.from_binary_path(str(positive/'reconstructed_runtime.mjb'))
data=mujoco.MjData(model)
wrist=model.body('right_wrist_yaw_link').id
cube=model.body('red_cube').id
runtime_fp=hashlib.sha256(model.geom_contype.tobytes()+model.geom_conaffinity.tobytes()+model.geom_margin.tobytes()+model.geom_solref.tobytes()+model.dof_armature.tobytes()).hexdigest()
assert runtime_fp==result['runtime_stamp']['in_memory_geometry_sha']
fingerprint_paths=[positive/'robot.xml',positive/'scene.xml',positive/'execution_plan.json',positive/'reference.npz',D/'out/side80_open7/plan.json',D/'wholehand_side.py',D/'execute_side.py',D/'GATES-v2.md']
plan=json.loads((D/'out/side80_open7/plan.json').read_text())
source=plan['ardy_source']
source_paths=[]
for key,value in source.items():
    if isinstance(value,str) and Path(value).is_file():source_paths.append(Path(value))

with np.load(positive/'trajectory.npz',allow_pickle=False) as p,np.load(negative/'trajectory.npz',allow_pickle=False) as n,np.load(repeat/'trajectory.npz',allow_pickle=False) as r:
    before=np.flatnonzero(p['time']<42.)
    paired={key:bool(np.array_equal(p[key][before],n[key][before])) for key in p.files}
    repeated={key:bool(np.array_equal(p[key],r[key])) for key in p.files}
    assert all(paired.values()) and all(repeated.values())
    positions=p['cube_pos'][before]
    initial=positions[0]
    drift={'max_xy_m':float(np.linalg.norm(positions[:,:2]-initial[:2],axis=1).max()),
           'max_xyz_m':float(np.linalg.norm(positions-initial,axis=1).max()),
           'last_xyz_minus_initial_m':(positions[-1]-initial).tolist(),
           'sample_dt_s':.02,'scope':'sampled evaluation-stage positions, before CLOSE t<42s'}
    local=[]
    for qpos in p['qpos']:
        data.qpos[:]=qpos;mujoco.mj_forward(model,data)
        local.append(data.xmat[wrist].reshape(3,3).T@(data.xpos[cube]-data.xpos[wrist]))
    local=np.array(local)
    lift=np.flatnonzero(p['time']>=46.)
    hold=np.flatnonzero(p['phase']=='HOLD')
    diag={'max_local_slip_from_first_saved_lift_m':float(np.linalg.norm(local[lift]-local[lift[0]],axis=1).max()),
          'max_local_slip_from_first_saved_hold_m':float(np.linalg.norm(local[hold]-local[hold[0]],axis=1).max()),
          'hold_saved_frames':len(hold),'not_runtime_gate':'post-step FK at 20ms; runtime gate evaluated every1ms'}
    assert np.max(np.abs(p['pad_forces']))==0
    ctrlrange=model.actuator_ctrlrange
    control_overrun=float(np.maximum(ctrlrange[:,0]-p['ctrl'],p['ctrl']-ctrlrange[:,1]).max())
    assert control_overrun<=1e-9
    joints=model.actuator_trnid[:,0]
    q=p['qpos'][:,model.jnt_qposadr[joints]]
    joint_overrun=max(0.,float(np.maximum(model.jnt_range[joints,0]-q,q-model.jnt_range[joints,1]).max()))
    arm_joints=model.actuator_trnid[22:29,0]
    arm_q=p['qpos'][:,model.jnt_qposadr[arm_joints]]
    arm_vel=p['qvel'][:,model.jnt_dofadr[arm_joints]]
    tracking={}
    for phase in ['REACH','CLOSE','GRIP_DWELL','TEST_LIFT','LIFT','HOLD']:
        mask=p['phase']==phase
        tracking[phase]={'sampled_max_arm_speed_rad_s':float(np.abs(arm_vel[mask]).max()),
                         'arm_reference_tracking_rms_rad':float(np.sqrt(np.mean((arm_q[mask]-p['body_reference'][mask,22:29])**2))),
                         'decoded_arm_target_tracking_rms_rad':float(np.sqrt(np.mean((arm_q[mask]-p['decoded_target'][mask,22:29])**2)))}
    assert model.neq==0 and model.nmocap==0

contacts=json.loads((positive/'contact_frames.json').read_text())
hold_contacts=[x for x in contacts if x['phase']=='HOLD']
thumb_min=min(x['thumb_load_N'] for x in hold_contacts)
opponent_min=min(x['index_middle_load_N'] for x in hold_contacts)
assert thumb_min>.1 and opponent_min>.1
report={'timestamp':datetime.datetime.now().astimezone().isoformat(),
        'environment':{'mujoco':mujoco.__version__,'model_origin':'posthoc reconstructed MJB; fingerprint matches runtime, not captured live'},
        'source_and_plan_hashes':{str(x):sha(x) for x in fingerprint_paths+source_paths},
        'ardy_source_plan_record':source,'before_close_paired_arrays_equal':paired,'repeat_arrays_equal':repeated,
        'preclose_cube_displacement':drift,'fk_sampled_diagnostic':diag,
        'sampled_ctrl_overrun':max(0.,control_overrun),'sampled_joint_limit_overrun_rad':joint_overrun,
        'sampled_hold_min_thumb_load_N':thumb_min,'sampled_hold_min_index_middle_load_N':opponent_min,
        'sampled_tracking_by_phase':tracking,
        'zero_spherical_pad_force':True,'neq':model.neq,'nmocap':model.nmocap,
        'early_contact_runtime_peak_N':result['preclose_cube_contact_peak_N'],
        'limits':['one geometry/placement/mass/trajectory, deterministic repeat only','contact forces from original runtime JSON, no reintegration force substitution','preclose contact exists; preclose displacement quantified not assumed zero']}
target=D/'native_audit2.json'
with target.open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
