"""Compare same-seed text inputs and actual SONIC/output traces, not names."""
import argparse
import json
from pathlib import Path
import numpy as np
from wave4_records import sha

p=argparse.ArgumentParser()
for item in ['control','newtext','output']:p.add_argument(item)
a=p.parse_args();root=Path(__file__).resolve().parent
for name in [a.control,a.newtext,a.output]:assert Path(name).name==name and len(name)<128
dest=root/'out'/a.output;assert dest.suffix=='.json' and not dest.exists()
folders=[root/'out'/name for name in [a.control,a.newtext]]
results=[json.loads((folder/'result.json').read_text()) for folder in folders]
x,y=results
for record in results:
    assert not record['body_action_override'] and not record['base_fixture'] and not record['ardy_off']
    assert record['ardy_arm_prior_consumed_by_sonic'] and not record['endpoint_branch_seed']
    assert record['motion_profile'] and record['user_corrections']==0
    assert record['source']['source_npz_sha256']==record['runtime_stamp']['library_sha']['native_npz']
    assert record['motion_profile']['roles']['reach']['source_npz_sha256']==record['source']['source_npz_sha256']
assert x['source']['text']!=y['source']['text']
assert x['motion_profile']['roles']['reach']['seed_from_generation_summary']==y['motion_profile']['roles']['reach']['seed_from_generation_summary']==43
for role in ['lift','hold','release']:
    assert x['motion_profile']['roles'][role]['source_npz_sha256']==y['motion_profile']['roles'][role]['source_npz_sha256']
for key in ['model_sha','scene_generator_sha','sys_executable','python_version','library_versions','mujoco_version','dt']:
    assert x['runtime_stamp'][key]==y['runtime_stamp'][key],key
allowed={'native_npz','input_profile'}
libdiff={key for key in set(x['runtime_stamp']['library_sha'])|set(y['runtime_stamp']['library_sha'])
    if x['runtime_stamp']['library_sha'].get(key)!=y['runtime_stamp']['library_sha'].get(key)}
assert libdiff==allowed,libdiff
for key in ['grip_preload_mm','independent_finger_kp_gain','neutral_shoulder_offset_rad',
    'no_grip','setdown_enabled','requested_postcapture_lift_height_m','ardy_nullspace_weight',
    'strict_execution_gate_enabled','c2_reference','direct_table','table_front_x_m']:
    assert x[key]==y[key],key
traces=[]
for folder in folders:
    with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
        assert 2<=len(z['time'])<=2250
        traces.append({key:z[key].copy() for key in ['time','phase','qpos','qvel','body_reference','decoded_motor_target','hand_reference','actuator_ctrl']})
rows={};times=traces[0]['time'];n=min(len(times),len(traces[1]['time']))
assert np.array_equal(times[:n],traces[1]['time'][:n])
for key in traces[0]:
    left,right=traces[0][key],traces[1][key]
    same_shape=left.shape==right.shape
    row=dict(shapes=[list(left.shape),list(right.shape)],exact=same_shape and bool(np.array_equal(left,right)),matched_clock_samples=n)
    if left.dtype.kind not in 'US':
        delta=abs(left[:n]-right[:n]);changed=delta>1e-9
        perframe=changed if changed.ndim==1 else changed.any(axis=tuple(range(1,changed.ndim)))
        indices=np.flatnonzero(perframe)
        row.update(common_prefix_max_abs_delta=float(delta.max()),first_change_time_s=float(times[indices[0]]) if len(indices) else None)
    rows[key]=row
assert rows['body_reference']['common_prefix_max_abs_delta']>1e-6
assert rows['decoded_motor_target']['common_prefix_max_abs_delta']>1e-6
answer=dict(physical_steps=0,source_episodes=[a.control,a.newtext],runtime_stamp=x['runtime_stamp'],
    script_sha256=sha(__file__),allowed_runtime_library_changes=sorted(libdiff),
    result_sha256=[sha(folder/'result.json') for folder in folders],
    trajectory_sha256=[sha(folder/'trajectory.npz') for folder in folders],
    texts=[r['source']['text'] for r in results],same_seed=43,arrays=rows,
    successes=[r['success'] for r in results],failed_gates=[[key for key,value in r['gates'].items() if not value] for r in results],
    fail_reasons=[r['fail_reason'] for r in results],
    hold_min_mm=[r['hold_min_lift_m']*1000 for r in results],hold_slip_mm=[r['hold_slip_m']*1000 for r in results],
    limitation='One matched scene per text and runtime. Changed inputs and outputs do not establish semantic correctness, ARDY necessity, broad generalization or real robot readiness; neutral-body/task scaffold remains explicit.')
dest.write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
