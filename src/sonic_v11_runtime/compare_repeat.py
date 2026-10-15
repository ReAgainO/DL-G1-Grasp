"""Read-only, bounded fresh-process repetition evidence; not random success rate."""
import argparse
import json
from pathlib import Path
import numpy as np
from wave4_records import sha

p=argparse.ArgumentParser();p.add_argument('first');p.add_argument('repeat');p.add_argument('output');args=p.parse_args()
root=Path(__file__).resolve().parent
for name in [args.first,args.repeat,args.output]:assert Path(name).name==name and len(name)<128
a_dir=root/'out'/args.first;b_dir=root/'out'/args.repeat;out=root/'out'/args.output
assert out.suffix=='.json' and not out.exists()
a=json.loads((a_dir/'result.json').read_text());b=json.loads((b_dir/'result.json').read_text())
assert a['success'] and b['success'] and all(a['gates'].values()) and all(b['gates'].values())
assert a['runtime_stamp']==b['runtime_stamp']
for key in ['source','motion_profile','grip_preload_mm','independent_finger_kp_gain','neutral_shoulder_offset_rad','no_grip','setdown_enabled']:
    assert a[key]==b[key],key
za=np.load(a_dir/'trajectory.npz',allow_pickle=False);zb=np.load(b_dir/'trajectory.npz',allow_pickle=False)
assert len(za['time'])<=2250 and len(zb['time'])<=2250
keys=['qpos','qvel','body_reference','decoded_motor_target','hand_reference','actuator_ctrl','time','phase']
arrays={}
for key in keys:
    x=za[key];y=zb[key];same_shape=x.shape==y.shape
    arrays[key]=dict(shapes=[list(x.shape),list(y.shape)],exact=same_shape and bool(np.array_equal(x,y)),
        maximum_abs_difference=float(np.max(abs(x-y))) if same_shape and x.dtype.kind not in 'US' else None)
answer=dict(physical_steps=0,runtime_stamp=a['runtime_stamp'],comparison_script_sha256=sha(__file__),
    result_sha256=[sha(a_dir/'result.json'),sha(b_dir/'result.json')],
    trajectory_sha256=[sha(a_dir/'trajectory.npz'),sha(b_dir/'trajectory.npz')],
    parameter_identity_verified=True,successes=[a['success'],b['success']],trajectory_arrays=arrays,
    hold_min_mm=[r['hold_min_lift_m']*1000 for r in [a,b]],hold_slip_mm=[r['hold_slip_m']*1000 for r in [a,b]],
    wall_seconds=[r['wall_s'] for r in [a,b]],
    limitation='Two fresh processes on identical deterministic scene/source/configuration; no stochastic robustness, generalization, confidence interval, controlled placing or real robot claim')
out.write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
