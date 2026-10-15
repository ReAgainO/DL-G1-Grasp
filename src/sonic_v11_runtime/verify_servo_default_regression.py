"""Full default-off dynamics comparison after optional face-servo deployment."""
import argparse,json
from pathlib import Path
import numpy as np
from wave4_records import sha
p=argparse.ArgumentParser();p.add_argument('baseline');p.add_argument('current');p.add_argument('output');a=p.parse_args();root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.baseline,a.current,a.output])
old_dir=root/'out'/a.baseline;new_dir=root/'out'/a.current
old=json.loads((old_dir/'result.json').read_text());new=json.loads((new_dir/'result.json').read_text())
assert old['runtime_stamp']['scene_generator_sha']=='e4450a7f13374938a5a81003666440aee6b1f1537a47112217cd42dd349de1b8'
assert new['runtime_stamp']['scene_generator_sha']=='28512909961057ab7f9c93144f633b5f0ca7f6b5aae9c1b05d80661baa59165c'
assert not new['branch_face_alignment_enabled'] and not new['face_aligned_servo']['enabled'] and new['face_aligned_servo']['calls']==0
assert old['success'] and new['success'] and old['gates']==new['gates']
for k in ['mujoco_version','sys_executable','python_version','model_sha','library_versions','dt']:assert old['runtime_stamp'][k]==new['runtime_stamp'][k],k
changed={k for k in set(old['runtime_stamp']['library_sha'])|set(new['runtime_stamp']['library_sha']) if old['runtime_stamp']['library_sha'].get(k)!=new['runtime_stamp']['library_sha'].get(k)}
assert changed=={'branch_face_ik'},changed
for key in ['hold_min_lift_m','hold_slip_m','duration_s','no_grip','pad_off','base_fixture','peak_external_force','user_corrections','grip_preload_mm','grip_face_half_mm','independent_finger_kp_gain','setdown_enabled','finger_table_clearance_mm']:assert old[key]==new[key],key
arrays={}
with np.load(old_dir/'trajectory.npz',allow_pickle=False) as x,np.load(new_dir/'trajectory.npz',allow_pickle=False) as y:
 assert len(x['time'])<=2250 and len(y['time'])<=2250
 assert np.array_equal(x['time'],y['time']) and np.array_equal(x['phase'],y['phase'])
 for k in ['qpos','qvel','body_reference','hand_reference','decoded_motor_target','raw_decoded_motor_target','applied_motor_target','actuator_ctrl']:
  assert x[k].shape==y[k].shape and np.isfinite(x[k]).all() and np.isfinite(y[k]).all()
  delta=float(np.max(abs(x[k]-y[k])));assert delta<=1e-8,(k,delta)
  arrays[k]=dict(shape=list(x[k].shape),exact=bool(np.array_equal(x[k],y[k])),max_delta=delta)
answer=dict(runtime_stamp=new['runtime_stamp'],physical_steps=0,baseline=a.baseline,current=a.current,
 baseline_result_sha256=sha(old_dir/'result.json'),current_result_sha256=sha(new_dir/'result.json'),
 verifier_sha256=sha(__file__),changed_libraries=sorted(changed),arrays=arrays,default_off_regression_passed=True,
 limitation='One strict-success input in MuJoCo3.2.7; verifies optional-servo disabled preserves this complete rollout. Not face-enabled generalization, placing, real-time or real robot proof.')
dest=root/'out'/a.output
with dest.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k!='runtime_stamp'},indent=2))
