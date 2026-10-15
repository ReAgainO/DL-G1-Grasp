"""Audit a same-source, same-scene ARDY composite ablation; no simulation."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
p=argparse.ArgumentParser()
p.add_argument('on');p.add_argument('off');p.add_argument('output_name')
args=p.parse_args()
assert all(Path(x).name==x and x not in ['.','..'] for x in vars(args).values())
root=Path(__file__).resolve().parent
folders=[root/'out'/args.on,root/'out'/args.off]
on,off=[json.loads((d/'result.json').read_text()) for d in folders]
st_on,st_off=[r['runtime_stamp'] for r in [on,off]]
assert not on['ardy_off'] and off['ardy_off']
assert st_on==st_off,'Runtime/source/model/dependency fingerprints differ; not matched'
keys=['base_fixture','direct_table','pinch_geometry','surface_capture','opposing_pad',
    'close_command_duration_s','c2_reference','endpoint_seed_selection',
    'right_arm_pd_kp_scale','right_arm_pd_kd_scale','lift_only_right_arm_damping_scale',
    'right_arm_gravity_feedforward_scale','postcapture_arm_pd_gain_scale',
    'postcapture_outer_servo_increment_cap_rad','hold_outer_servo_frozen',
    'grip_frame_lift','lock_grip','sonic_armature','passive_free_diagnostic',
    'phase_clips_loaded','preclosure_capture_radius_m','preclosure_contact_close_enabled',
    'preclosure_contact_dwell_s','alignment_time_limit_s','requested_postcapture_lift_height_m',
    'body_action_override','no_grip','pad_off','ardy_nullspace_weight',
    'table_front_x_m','table_back_x_m','grip_preload_mm','independent_finger_kp_gain']
assert all(on.get(key)==off.get(key) for key in keys),'Task/control configuration differs'
assert on['reference_filter']['continue_certified_enabled']==off['reference_filter']['continue_certified_enabled']
assert on['source']['source_npz_sha256']==off['source']['source_npz_sha256']
assert on['ardy_arm_prior_consumed_by_sonic'] and on['native_path_consumed_by_sonic']
assert not off['ardy_arm_prior_consumed_by_sonic'] and not off['native_path_consumed_by_sonic']
assert on['phase_clips_consumed'] and not off['phase_clips_consumed']
assert off['native_derived_endpoint_seed_held_constant_for_ablation']
z_on,z_off=[np.load(d/'trajectory.npz',allow_pickle=False) for d in folders]
n=min(len(z_on['time']),len(z_off['time']))
assert n>0 and n<=2250 and np.array_equal(z_on['time'][:n],z_off['time'][:n])
delta=abs(z_on['qpos'][:n]-z_off['qpos'][:n]).max(axis=1)
first=np.flatnonzero(delta>1e-12)
assert len(first)>0,'ON/OFF trajectories identical; control invalid'
ref_delta=float(abs(z_on['body_reference'][:n]-z_off['body_reference'][:n]).max())
assert ref_delta>1e-5,'Ablation did not alter SONIC reference'
out=root/'out'/args.output_name
out.mkdir()
answer=dict(physical_steps=0,paired_runtime_stamp=st_on,analysis_source_sha=sha(__file__),
    result_sha256={'on':sha(folders[0]/'result.json'),'off':sha(folders[1]/'result.json')},
    configuration_keys_verified=keys,same_source_scene_weights_and_simulator=True,
    first_saved_pose_divergence_s=float(z_on['time'][first[0]]),max_body_reference_difference_rad=ref_delta,
    success_on=on['success'],success_off=off['success'],
    hold_min_lift_on_m=on['hold_min_lift_m'],off_failure=off['fail_reason'],
    off_max_lift_m=off['max_lift_m'],off_phase_clips_consumed=off['phase_clips_consumed'],
    limitation='Composite path/prior/timing ablation only, MuJoCo'+st_on['mujoco_version']+(' fixed-base' if on['base_fixture'] else ' free-base')+' setup. Native-derived endpoint seed held constant. Not a fully ARDY-independent baseline, not general causality, no real-robot claim.')
destination=folders[0]/'release-destination.json'
answer['on_final_table_supported']=json.loads(destination.read_text())['final_table_supported'] if destination.exists() else None
answer['success_fields_use_original_gate_version']=on['gate_definition_version']
answer['release_gate_caveat']='Original final_supported allows floor/table. Table return must be reported separately; no historical result overwritten.'
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k not in ['paired_runtime_stamp','configuration_keys_verified']},indent=2))
