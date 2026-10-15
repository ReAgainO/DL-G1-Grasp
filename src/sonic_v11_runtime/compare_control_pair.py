"""Matched-source finger/negative-control evidence; zero integration."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import mujoco
import numpy as np

p=argparse.ArgumentParser()
p.add_argument('on');p.add_argument('off');p.add_argument('output_name')
p.add_argument('--factor',choices=['independent_finger_kp_gain','no_grip','pad_off'],required=True)
a=p.parse_args()
assert all(Path(x).name==x and x not in ['.','..'] for x in [a.on,a.off,a.output_name])
root=Path(__file__).resolve().parent
folders=[root/'out'/a.on,root/'out'/a.off]
on,off=[json.loads((folder/'result.json').read_text()) for folder in folders]
assert on['runtime_stamp']==off['runtime_stamp'],'Not matched source/model/env/weights'
keys=['base_fixture','direct_table','pinch_geometry','surface_capture','opposing_pad',
    'close_command_duration_s','c2_reference','endpoint_seed_selection',
    'right_arm_pd_kp_scale','right_arm_pd_kd_scale','lift_only_right_arm_damping_scale',
    'right_arm_gravity_feedforward_scale','postcapture_arm_pd_gain_scale',
    'postcapture_outer_servo_increment_cap_rad','hold_outer_servo_frozen',
    'grip_frame_lift','lock_grip','sonic_armature','passive_free_diagnostic',
    'phase_clips_loaded','preclosure_capture_radius_m','preclosure_contact_close_enabled',
    'preclosure_contact_dwell_s','alignment_time_limit_s','requested_postcapture_lift_height_m',
    'body_action_override','no_grip','pad_off','ardy_nullspace_weight','ardy_off',
    'table_front_x_m','table_back_x_m','grip_preload_mm','independent_finger_kp_gain']
assert on[a.factor]!=off[a.factor],'Factor was not changed'
assert all(on.get(key)==off.get(key) for key in keys if key!=a.factor),'Other task factor differs'
assert on['source']['source_npz_sha256']==off['source']['source_npz_sha256']
assert on['reference_filter']['continue_certified_enabled']==off['reference_filter']['continue_certified_enabled']
z_on,z_off=[np.load(folder/'trajectory.npz',allow_pickle=False) for folder in folders]
n=min(len(z_on['time']),len(z_off['time']))
assert 0<n<=2250 and np.array_equal(z_on['time'][:n],z_off['time'][:n])
delta=abs(z_on['qpos'][:n]-z_off['qpos'][:n]).max(axis=1)
fork=np.flatnonzero(delta>1e-12)
assert len(fork)>0,'Control identical; cannot claim effective factor'
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    dt=.002,model_sha=on['runtime_stamp']['model_sha'],scene_generator_sha=sha(__file__),
    library_sha={'on':sha(folders[0]/'result.json'),'off':sha(folders[1]/'result.json'),
        'on_trajectory':sha(folders[0]/'trajectory.npz'),'off_trajectory':sha(folders[1]/'trajectory.npz')})
answer=dict(runtime_stamp=stamp,paired_runtime_stamp=on['runtime_stamp'],physical_steps=0,
    factor=a.factor,factor_on=on[a.factor],factor_off=off[a.factor],configuration_keys_verified=keys,
    same_source_model_weights_environment=True,first_saved_pose_divergence_s=float(z_on['time'][fork[0]]),
    success_on=on['success'],success_off=off['success'],
    hold_min_lift_on_m=on['hold_min_lift_m'],hold_min_lift_off_m=off['hold_min_lift_m'],
    off_failure=off['fail_reason'],off_max_lift_m=off['max_lift_m'],
    limitation='Current MuJoCo '+on['runtime_stamp']['mujoco_version']+' nominal scene only. Selected-finger KP gain also sets KD by square-root convention. No generalized physical causality, COM/COP, vision or real-robot claim.')
destination=folders[0]/'release-destination.json'
answer['on_final_table_supported']=json.loads(destination.read_text())['final_table_supported'] if destination.exists() else None
answer['success_fields_use_original_gate_version']=on['gate_definition_version']
answer['release_gate_caveat']='Original final_supported allows floor/table; table return must be reported separately.'
out=root/'out'/a.output_name
out.mkdir()
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k not in ['runtime_stamp','paired_runtime_stamp','configuration_keys_verified']},indent=2))
