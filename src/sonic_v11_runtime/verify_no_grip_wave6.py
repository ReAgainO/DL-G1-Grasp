"""Matched no-grip source, actual branch execution, and observable divergence."""
import json
from pathlib import Path
import numpy as np
from wave4_records import sha

root=Path(__file__).resolve().parent
on=root/'out/w6_branchpreload15_near327';off=root/'out/w6_branchpreload15_nogrip327'
out=root/'out/w6-no-grip-comparison327.json';assert not out.exists()
a=json.loads((on/'result.json').read_text());b=json.loads((off/'result.json').read_text())
assert a['success'] and not b['success'] and b['no_grip'] and not a['no_grip']
assert a['runtime_stamp']==b['runtime_stamp']
for key in ['independent_finger_kp_gain','grip_preload_mm','neutral_shoulder_offset_rad','source','motion_profile','post_clearance_native_branch','post_clearance_branch_servo_enabled']:
    if key=='post_clearance_native_branch':
        assert a[key]['selected']==b[key]['selected']
    else:assert a[key]==b[key],key
za=np.load(on/'trajectory.npz',allow_pickle=False);zb=np.load(off/'trajectory.npz',allow_pickle=False)
assert len(za['time'])<=2250 and len(zb['time'])<=2250
close=next(e['time_s'] for e in a['events'] if e['phase']=='CLOSE')
assert close==next(e['time_s'] for e in b['events'] if e['phase']=='CLOSE')
n=int(np.count_nonzero(za['time']<close));assert n>1000
keys=['qpos','qvel','body_reference','decoded_motor_target','hand_reference','actuator_ctrl','time','phase']
prefix={k:bool(np.array_equal(za[k][:n],zb[k][:n])) for k in keys}
assert all(prefix.values()),'Not a matched pre-intervention trajectory'
length=min(len(za['time']),len(zb['time']))
hand_difference=float(np.max(abs(za['hand_reference'][n:length]-zb['hand_reference'][n:length])))
assert hand_difference>1e-6,'No-grip intervention did not change finger references'
answer=dict(physical_steps=0,runtime_stamp=a['runtime_stamp'],comparison_script_sha256=sha(__file__),
    source_result_sha256={'on':sha(on/'result.json'),'off':sha(off/'result.json')},
    matched_preclose_frames=n,preclose_arrays_exact=prefix,postclose_hand_reference_max_difference_rad=hand_difference,
    on_success=a['success'],off_success=b['success'],on_hold_min_m=a['hold_min_lift_m'],off_hold_min_m=b['hold_min_lift_m'],
    on_hold_slip_m=a['hold_slip_m'],off_hold_slip_m=b['hold_slip_m'],
    limitation='3.2.7 matched no-grip control only; same new-route control in3.14 not yet tested. No ARDY necessity or generalization claim.')
out.write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
