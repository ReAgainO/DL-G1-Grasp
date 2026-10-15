"""Report whether optional table geometry actually changed controls; no forced PASS."""
import argparse
import json
from pathlib import Path
import numpy as np
from wave4_records import sha

p=argparse.ArgumentParser()
for key in ['original','constrained','output']:p.add_argument(key)
a=p.parse_args();root=Path(__file__).resolve().parent
assert all(Path(name).name==name and len(name)<128 for name in [a.original,a.constrained,a.output])
dest=root/'out'/a.output;assert dest.suffix=='.json' and not dest.exists()
folders=[root/'out'/name for name in [a.original,a.constrained]]
results=[json.loads((folder/'result.json').read_text()) for folder in folders];x,y=results
assert x.get('finger_table_clearance_mm',0)==0 and y['finger_table_clearance_mm']==1
for key in ['source','motion_profile','grip_preload_mm','independent_finger_kp_gain','requested_postcapture_lift_height_m',
    'neutral_shoulder_offset_rad','no_grip','setdown_enabled','direct_table','table_front_x_m','ardy_nullspace_weight']:
    assert x[key]==y[key],key
for key in ['model_sha','mujoco_version','sys_executable','python_version','library_versions','dt']:
    assert x['runtime_stamp'][key]==y['runtime_stamp'][key],key
assert x['runtime_stamp']['scene_generator_sha']=='93a9f38949bb542c378b900de45e8209c85b703996ef09113973d02a4eeec13e'
assert y['runtime_stamp']['scene_generator_sha']=='f01c16cc913983c9f2befd2abd49c9694f6de9f53fe59407ee42d4225136e219'
diff={key for key in set(x['runtime_stamp']['library_sha'])|set(y['runtime_stamp']['library_sha'])
    if x['runtime_stamp']['library_sha'].get(key)!=y['runtime_stamp']['library_sha'].get(key)}
assert diff=={'adaptive_hand','cycle_latency','finger_clearance'}
traces=[]
for folder in folders:
    with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
        assert 2<=len(z['time'])<=2250
        traces.append({key:z[key].copy() for key in ['qpos','qvel','body_reference','decoded_motor_target','hand_reference','actuator_ctrl','time','phase']})
arrays={}
for key in traces[0]:
    left,right=traces[0][key],traces[1][key];same_shape=left.shape==right.shape
    arrays[key]=dict(shapes=[list(left.shape),list(right.shape)],exact=same_shape and bool(np.array_equal(left,right)),
        maximum_abs_delta=float(abs(left-right).max()) if same_shape and left.dtype.kind not in 'US' else None)
answer=dict(physical_steps=0,source_episodes=[a.original,a.constrained],runtime_stamp=x['runtime_stamp'],
    script_sha256=sha(__file__),result_sha256=[sha(folder/'result.json') for folder in folders],
    actuator_commands_changed=not arrays['actuator_ctrl']['exact'],hand_references_changed=not arrays['hand_reference']['exact'],
    arrays=arrays,successes=[r['success'] for r in results],
    table_contact_max_N=[r['balance_audit_summary']['robot_table_all_max_normal_N'] for r in results],
    interpretation='If arrays are identical, the1mm setting is NOT an effective physical improvement in this case. Same geometry/default refactor also independently preserves originalnear. Code/observer changed, so use a same-new-code OFF trial before making causal benefit claims.')
dest.write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
