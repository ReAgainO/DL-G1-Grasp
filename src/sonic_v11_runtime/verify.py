"""Independent audit of saved kinematics, execution, holding and negative controls."""
import json,sys
from pathlib import Path
import numpy as np,mujoco
import trajectory as tr
root=Path(sys.argv[1]);report={'kinematic':[],'tracking':[],'grasp':[],'pairs':[]}
for name in ['repaired_guided_s42','repaired_guided_cfg8_s42']:
 folder=root/'out'/name;r=json.loads((folder/'result.json').read_text());z=np.load(folder/'reference.npz',allow_pickle=False)
 st=json.loads(str(z['runtime_stamp']));assert st==r['runtime_stamp']
 assert r['success'] and len(z['time'])<=45001 and np.isfinite(z['q']).all()
 m,d,ids,aq,av,qa,va,ix=tr.robot(root/'model/scene_fixed_grasp.xml')
 lo,hi=m.jnt_range[m.dof_jntid[av],0],m.jnt_range[m.dof_jntid[av],1]
 assert (z['q']>=lo).all() and (z['q']<=hi).all()
 v=np.diff(z['q'],axis=0)/.002;a=np.diff(v,axis=0)/.002
 assert np.max(abs(v))<=.601 and np.max(abs(a))<=1.501
 report['kinematic'].append(dict(run=name,runtime_stamp=st,fd_velocity_max=float(np.max(abs(v))),fd_accel_max=float(np.max(abs(a))),
                                  duration_s=r['duration_s'],source_repair_rms_rad=r['raw_repair_rms_rad']))
for name in ['legacy327_v2','legacy314','ff327','ff314','ff8_327']:
 folder=root/'out'/name;r=json.loads((folder/'result.json').read_text());z=np.load(folder/'trajectory.npz',allow_pickle=False)
 assert json.loads(str(z['runtime_stamp']))==r['runtime_stamp']
 source=np.load(str(z['reference']),allow_pickle=False)
 assert np.max(abs(z['right_arm_targets']-source['q'][::20]))<1e-12
 m,d,ids,aq,av,qa,va,ix=tr.robot(folder/'scene_fixed_grasp.xml')
 err=z['qpos'][:,aq]-z['right_arm_targets'];rms=float(np.sqrt(np.mean(err[z['time']>.5]**2)))
 assert abs(rms-r['tracking_rms_rad'])<1e-10
 report['tracking'].append(dict(run=name,runtime_stamp=r['runtime_stamp'],rms_rad=rms,success=r['success'],wrist_max_m=r['wrist_tracking_max_m']))
for version in ['327','314']:
 for mode in ['on','off','pads_off']:
  name='c_'+mode+version;folder=root/'out'/name;r=json.loads((folder/'result.json').read_text());z=np.load(folder/'trajectory.npz',allow_pickle=False)
  assert json.loads(str(z['runtime_stamp']))==r['runtime_stamp']
  with (folder/'telemetry.csv').open() as f:assert json.loads(f.readline().split('=',1)[1])==r['runtime_stamp']
  rows=np.loadtxt(folder/'telemetry.csv',delimiter=',',comments='#')
  events={e['phase']:e['time_s'] for e in r['events']}
  mask=(rows[:,0]>=events['HOLD']+.02)&(rows[:,0]<=events['RELEASE']);h=rows[mask]
  assert len(h)>=950
  assert abs(np.min(h[:,3])-.7745-r['hold_min_lift_m'])<1e-9
  assert int(np.min((h[:,7:10]>.01).sum(axis=1)))==r['hold_min_contact_bodies']
  assert abs(np.max(h[:,10])-r['hold_max_support_force_N'])<1e-9
  assert r['success']==(mode=='on')
  m,d,ids,aq,av,qa,va,ix=tr.robot(folder/'scene_fixed_grasp.xml')
  assert m.neq==0 and (m.jnt_type==mujoco.mjtJoint.mjJNT_FREE).sum()==1
  plan=np.load(root/'out/task_plan_continuous/plan.npz',allow_pickle=False)
  expected=[]
  for t,phase in zip(z['time'],z['phase']):
   step=round(t/.002)-1;elapsed=step*.002-events[str(phase)]
   arr='down' if phase in ['PREGRASP','DESCEND','ALIGN','CLOSE'] else 'up'
   idx=0 if phase=='PREGRASP' else min(max(int(elapsed/.002),0),len(plan[arr+'_q'])-1) if phase in ['DESCEND','LIFT'] else len(plan[arr+'_q'])-1
   expected.append(plan[arr+'_q'][idx])
  target_error=float(np.max(abs(np.asarray(expected)-z['right_arm_targets'])))
  assert target_error<1e-10,target_error
  report['grasp'].append(dict(run=name,runtime_stamp=r['runtime_stamp'],success=r['success'],max_lift_m=r['max_lift_m'],
                             hold_min_lift_m=r['hold_min_lift_m'],two_finger_min=r['hold_min_contact_bodies'],
                             normal_min_N=r['hold_min_total_finger_normal_force_N'],slip_m=r['hold_slip_m'],
                             target_vs_plan_max_error_rad=target_error,hold_sample_count=len(h)))
 on=np.load(root/'out'/('c_on'+version)/'trajectory.npz',allow_pickle=False)
 for mode in ['off','pads_off']:
  off=np.load(root/'out'/('c_'+mode+version)/'trajectory.npz',allow_pickle=False)
  eq=on['qpos'].shape==off['qpos'].shape and np.array_equal(on['qpos'],off['qpos'])
  assert not eq,'Negative physical trajectories did not diverge'
  targets_eq=on['right_arm_targets'].shape==off['right_arm_targets'].shape and np.array_equal(on['right_arm_targets'],off['right_arm_targets'])
  report['pairs'].append(dict(version=version,negative=mode,physical_trajectory_differs=True,arm_targets_exactly_equal=targets_eq))
zero=[]
for name in ['zero327','zero314']:
 r=json.loads((root/'out'/name/'result.json').read_text());zero.append(dict(run=name,success=r['success'],hold_min_lift_m=r['hold_min_lift_m'],runtime_stamp=r['runtime_stamp']))
report['zero_ardy_ablation']=zero
report['interpretation']='If zero-ARDY also succeeds, successful hybrid grasp does NOT establish necessity or benefit of ARDY.'
report['all_checks_pass']=True
(root/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
