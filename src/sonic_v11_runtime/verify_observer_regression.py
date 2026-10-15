"""Verify observer/default geometry refactor did not alter executed controls."""
import argparse
import json
from pathlib import Path
import numpy as np
from wave4_records import sha

p=argparse.ArgumentParser()
for key in ['before','after','output']:p.add_argument(key)
a=p.parse_args();root=Path(__file__).resolve().parent
assert all(Path(name).name==name and len(name)<128 for name in [a.before,a.after,a.output])
out=root/'out'/a.output;assert out.suffix=='.json' and not out.exists()
folders=[root/'out'/name for name in [a.before,a.after]]
x,y=[json.loads((folder/'result.json').read_text()) for folder in folders]
assert x['success'] and y['success'] and all(y['gates'].values())
assert y['finger_table_clearance_mm']==0 and not x.get('finger_table_clearance_mm',0)
for key in ['model_sha','mujoco_version','sys_executable','python_version','library_versions','dt']:
    assert x['runtime_stamp'][key]==y['runtime_stamp'][key],key
assert x['runtime_stamp']['scene_generator_sha']=='93a9f38949bb542c378b900de45e8209c85b703996ef09113973d02a4eeec13e'
assert y['runtime_stamp']['scene_generator_sha']=='f01c16cc913983c9f2befd2abd49c9694f6de9f53fe59407ee42d4225136e219'
diff={key for key in set(x['runtime_stamp']['library_sha'])|set(y['runtime_stamp']['library_sha'])
    if x['runtime_stamp']['library_sha'].get(key)!=y['runtime_stamp']['library_sha'].get(key)}
assert diff=={'adaptive_hand','cycle_latency','finger_clearance'},diff
for key in ['source','motion_profile','grip_preload_mm','independent_finger_kp_gain','requested_postcapture_lift_height_m',
    'neutral_shoulder_offset_rad','no_grip','setdown_enabled','direct_table','table_front_x_m','ardy_nullspace_weight']:
    assert x[key]==y[key],key
zs=[]
for folder in folders:
    with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
        assert 2<=len(z['time'])<=2250
        zs.append({key:z[key].copy() for key in ['qpos','qvel','body_reference','decoded_motor_target','hand_reference','actuator_ctrl','time','phase']})
arrays={}
for key in zs[0]:
    left,right=zs[0][key],zs[1][key];assert left.shape==right.shape,key
    exact=bool(np.array_equal(left,right));delta=float(abs(left-right).max()) if left.dtype.kind not in 'US' else None
    assert exact if delta is None else delta<=1e-8,(key,delta)
    arrays[key]=dict(shape=list(left.shape),exact=exact,maximum_abs_delta=delta)
latency=y['execution_cycle_latency']
assert latency['actual_physics_steps']==json.loads((folders[1]/'contact-audit.json').read_text())['physics_steps']
assert latency['aborted_iterations_without_physics']==0 and not latency['unfinished_observation']
assert latency['complete_50Hz_cycles']['samples']==latency['actual_physics_steps']//10
answer=dict(physical_steps=0,default_control_trace_preserved_within_1e_minus8=True,
    arrays=arrays,allowed_library_changes=sorted(diff),
    result_sha256=[sha(folder/'result.json') for folder in folders],
    trajectory_sha256=[sha(folder/'trajectory.npz') for folder in folders],
    old_and_new_successes=[x['success'],y['success']],latency=latency,
    simulation_s=y['duration_s'],whole_run_wall_s=y['wall_s'],policy_p95_ms=y['policy_p95_ms'],
    limitation='Same deterministic scene/source/parameters; observer and disabled geometry feature preserve this trace only. Policy-only p95 is not20ms full-cycle compliance. No real-time service, new-text generalization or enabled table-constraint claim.')
out.write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
