"""Verify the actual changed branch is reached, with exact pre-intervention parity."""
import argparse,json
from pathlib import Path
import numpy as np
from wave4_records import sha
p=argparse.ArgumentParser();p.add_argument('baseline');p.add_argument('current');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.baseline,a.current,a.output])
old_dir=root/'out'/a.baseline;new_dir=root/'out'/a.current
old=json.loads((old_dir/'result.json').read_text());new=json.loads((new_dir/'result.json').read_text())
assert old['runtime_stamp']['scene_generator_sha']=='e4450a7f13374938a5a81003666440aee6b1f1537a47112217cd42dd349de1b8'
assert new['runtime_stamp']['scene_generator_sha']=='28512909961057ab7f9c93144f633b5f0ca7f6b5aae9c1b05d80661baa59165c'
assert new['face_aligned_servo']['enabled'] and new['face_aligned_servo']['calls']>0
assert old['branch_face_alignment_enabled'] and new['branch_face_alignment_enabled']
for k in ['mujoco_version','sys_executable','python_version','model_sha','library_versions','dt']:assert old['runtime_stamp'][k]==new['runtime_stamp'][k],k
assert old['motion_profile']==new['motion_profile']
changed={k for k in set(old['runtime_stamp']['library_sha'])|set(new['runtime_stamp']['library_sha']) if old['runtime_stamp']['library_sha'].get(k)!=new['runtime_stamp']['library_sha'].get(k)}
assert changed=={'branch_face_ik'},changed
first=new['face_aligned_servo']['records'][0]['time_s'];arrays={}
with np.load(old_dir/'trajectory.npz',allow_pickle=False) as x,np.load(new_dir/'trajectory.npz',allow_pickle=False) as y:
 assert len(x['time'])<=2250 and len(y['time'])<=2250
 ix=x['time']<=first-1e-8;iy=y['time']<=first-1e-8
 assert ix.sum()==iy.sum() and ix.sum()>100
 assert np.array_equal(x['time'][ix],y['time'][iy]) and np.array_equal(x['phase'][ix],y['phase'][iy])
 for k in ['qpos','qvel','body_reference','hand_reference','decoded_motor_target','raw_decoded_motor_target','applied_motor_target','actuator_ctrl']:
  left=x[k][ix];right=y[k][iy];assert np.isfinite(left).all() and np.isfinite(right).all()
  delta=float(np.max(abs(left-right)));assert delta<=1e-8,(k,delta)
  arrays[k]=dict(shape=list(left.shape),exact=bool(np.array_equal(left,right)),max_delta=delta)
answer=dict(runtime_stamp=new['runtime_stamp'],physical_steps=0,baseline=a.baseline,current=a.current,
 baseline_result_sha256=sha(old_dir/'result.json'),current_result_sha256=sha(new_dir/'result.json'),
 verifier_sha256=sha(__file__),first_face_servo_time_s=first,pre_intervention_arrays=arrays,
 branch_reached=True,changed_libraries=sorted(changed),prefix_regression_passed=True,
 limitation='Pre-intervention matching and reached-branch evidence only; does not certify task success or causation/generalization beyond this single matched pair/version.')
dest=root/'out'/a.output
with dest.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k!='runtime_stamp'},indent=2))
