"""Bounded saved-state reference and 500Hz load diagnostic; zero integration."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import mujoco
import numpy as np
from setdown_plan import SetdownPlan
from wave4_records import sha

p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.episode,a.output])
folder=root/'out'/a.episode;r=json.loads((folder/'result.json').read_text())
assert r['setdown_enabled'] and r['runtime_stamp']['mujoco_version']==mujoco.__version__
assert sha(folder/'scene.xml')==r['runtime_stamp']['model_sha']['scene']
assert sha(folder/'g1_free_grasp.xml')==r['runtime_stamp']['model_sha']['robot']
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'));d=mujoco.MjData(m);f=mujoco.MjData(m)
wrist=m.body('right_wrist_yaw_link').id;cube=m.body('red_cube').id
names=r['source']['joint_names'];assert len(names)==29
bq=m.jnt_qposadr[[m.joint(n).id for n in names]];aq=bq[22:29]
with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
    assert 2<=len(z['time'])<=2250
    assert json.loads(str(z['runtime_stamp']))==r['runtime_stamp']
    qs=z['qpos'].copy();refs=z['body_reference'].copy();motors=z['decoded_motor_target'].copy()
    phases=z['phase'].copy();times=z['time'].copy();targets=z['wrist_target'].copy()
event={x['phase']:x['time_s'] for x in r['events']};start=event['SETDOWN']
plan=SetdownPlan(r['setdown_plan']['start_m'],r['setdown_plan']['goal_m'],r['setdown_plan']['duration_s'])
candidate=np.where((times>=start-.25)&(times<=start+1.))[0]
tail=np.where(phases=='SETDOWN')[0]
indices=np.unique(np.r_[candidate,tail[np.unique(np.linspace(0,len(tail)-1,min(160,len(tail))).astype(int))]])
assert len(indices)<=200
samples=[]
for i in indices:
    d.qpos[:]=qs[i];mujoco.mj_forward(m,d)
    actual=d.xpos[wrist].copy();R=d.xmat[wrist].reshape(3,3).copy()
    predicted=[]
    for body in [refs[i],motors[i]]:
        f.qpos[:]=d.qpos;f.qpos[bq]=body;mujoco.mj_forward(m,f)
        predicted.append(f.xpos[wrist].copy())
    target=targets[i]
    samples.append(dict(time_s=float(times[i]),phase=str(phases[i]),wrist_actual_m=actual.tolist(),cube_actual_m=d.xpos[cube].tolist(),
        wrist_target_m=target.tolist() if np.isfinite(target).all() else None,
        planned_minus_actual_mm=(1000*(target-actual)).tolist() if np.isfinite(target).all() else None,
        virtual_reference_wrist_m=predicted[0].tolist(),decoded_target_fk_wrist_m=predicted[1].tolist(),
        actual_minus_reference_arm_rad=(qs[i,aq]-refs[i,22:29]).tolist(),actual_minus_decoder_arm_rad=(qs[i,aq]-motors[i,22:29]).tolist(),
        cube_relative_to_actual_wrist_m=(R.T@(d.xpos[cube]-actual)).tolist()))
first=int(tail[0]);last_hold=int(np.where(phases=='HOLD')[0][-1])
d.qpos[:]=qs[last_hold];mujoco.mj_forward(m,d);near_actual=d.xpos[wrist].copy()
with gzip.open(folder/'telemetry.csv.gz','rt') as f:
    assert json.loads(f.readline().split('=',1)[1])==r['runtime_stamp']
    header=f.readline().strip().removeprefix('# ').split(',')
    rows=[]
    for row in csv.reader(f):
        assert len(rows)<45000
        rows.append([float(x) for x in row])
v=np.asarray(rows);assert np.isfinite(v).all();col={n:i for i,n in enumerate(header)}
t=v[:,col['time_s']];opposed=(v[:,col['thumb_force_N']]>.01)&(v[:,col['middle_force_N']]>.01)
windows={}
for label,lo,hi in [('hold_last250ms',start-.25,start),('setdown_first250ms',start,start+.25),('setdown_first500ms',start,start+.5),('setdown_first1s',start,start+1.)]:
    idx=np.where((t>lo)&(t<=hi))[0]
    rel=v[idx,4:7];slip=np.linalg.norm(rel-rel[0],axis=1)
    windows[label]=dict(samples=len(idx),opposed_loaded_fraction=float(opposed[idx].mean()),
        minimum_thumb_N=float(v[idx,col['thumb_force_N']].min()),minimum_middle_N=float(v[idx,col['middle_force_N']].min()),
        maximum_relative_slip_mm=float(slip.max()*1000),cube_z_first_m=float(v[idx[0],col['cube_z_m']]),cube_z_last_m=float(v[idx[-1],col['cube_z_m']]))
first_bad=np.where((t>start)&(~opposed))[0]
answer=dict(runtime_stamp=r['runtime_stamp'],physical_steps=0,script_sha256=sha(__file__),episode=a.episode,
    result_sha256=sha(folder/'result.json'),trajectory_sha256=sha(folder/'trajectory.npz'),telemetry_sha256=sha(folder/'telemetry.csv.gz'),
    sample_bound=200,sample_count=len(samples),telemetry_sample_count=len(rows),setdown_start_s=start,
    setdown_plan=plan.audit(),last_hold_sample_s=float(times[last_hold]),first_setdown_sample_s=float(times[first]),
    nominal_start_minus_last_hold_actual_wrist_mm=(1000*(plan.start-near_actual)).tolist(),
    wrist_reference_step_hold_to_setdown_mm=(1000*(targets[first]-targets[last_hold])).tolist(),
    first_opposed_load_gap_after_setdown_s=float(t[first_bad[0]]-start) if len(first_bad) else None,
    windows_500Hz=windows,samples_25Hz=samples,
    limitation='500Hz force/slip windows are original physics telemetry; wrist/reference/decoder FK is sampled25Hz, with unlogged exact phase boundary. Does not prove a causal root cause, policy-history resume, force closure, or controlled placing. No new physics.')
dest=root/'out'/a.output;assert dest.suffix=='.json'
with dest.open('x') as f:f.write(json.dumps(answer,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k not in ['samples_25Hz','runtime_stamp']},indent=2,allow_nan=False))
