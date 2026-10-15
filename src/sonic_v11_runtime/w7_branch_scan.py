"""Bounded static candidate scan at saved state; no mj_step or dynamics claim."""
import argparse,copy,json,zipfile,sys,platform
from pathlib import Path
import mujoco,numpy as np
import native_branch,source_physics_core as core
from adaptive_hand import AdaptiveHand
from motion_input import ArdyMotion
from sonic_grasp import ik,pinch_center
from wave4_records import sha
p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.episode,a.output])
folder=root/'out'/a.episode;dest=root/'out'/a.output;assert dest.suffix=='.json' and not dest.exists()
r=json.loads((folder/'result.json').read_text());stamp=r['runtime_stamp']
assert stamp['mujoco_version']==mujoco.__version__ and sha(folder/'scene.xml')==stamp['model_sha']['scene']
assert sha(root/'native_branch.py')==stamp['library_sha']['native_branch']
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'));d=mujoco.MjData(m)
with zipfile.ZipFile(folder/'trajectory.npz') as z:assert len(z.infolist())<40 and sum(f.file_size for f in z.infolist())<128*1024**2
with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
 assert z['qpos'].shape[1]==m.nq and 2<=len(z['time'])<=2250
 d.qpos[:]=z['qpos'][-1];d.qvel[:]=z['qvel'][-1];saved=float(z['time'][-1]);initial_cube=z['qpos'][0,-7:-4].copy()
gap=r['duration_s']-saved;assert 0<=gap<=.041
entry=r['motion_profile']['roles']['reach'];source=Path(entry['source_npz'])
assert source.resolve().is_relative_to(root) and sha(source)==entry['source_npz_sha256']
motion=ArdyMotion(source,check_csv=source.with_suffix('.csv'))
assert 2<=len(motion.qpos)<=2250
arm_jids=np.array([m.joint(n).id for n in motion.joint_names[22:29]]);aq=m.jnt_qposadr[arm_jids];av=m.jnt_dofadr[arm_jids]
hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];wrist=m.body('right_wrist_yaw_link').id;cube=m.body('red_cube').id
geo=mujoco.MjData(m);geo.qpos[:]=d.qpos;geo.qpos[:3]=[0,0,.74];geo.qpos[3:7]=[1,0,0,0]
bq=m.jnt_qposadr[np.array([m.joint(n).id for n in motion.joint_names])];xs=[]
for q in motion.qpos:
 geo.qpos[bq]=q[7:];mujoco.mj_forward(m,geo);xs.append(float(geo.xpos[wrist,0]))
common_frame=int(np.argmax(xs));common=motion.qpos[common_frame,29:36].copy()
hand=core.CLOSED.copy();hand[2]=-.88;target=initial_cube+np.array([0,0,.10]);opponent=2
assert r['opposing_pad']=='right_middle_fingertip'
mujoco.mj_forward(m,d);R=d.xmat[cube].reshape(3,3).copy()
table=m.geom('table_top').id;bodies={m.body('pelvis').id}
for body in range(1,m.nbody):
 if int(m.body_parentid[body]) in bodies:bodies.add(body)
geoms=[g for g in range(m.ngeom) if int(m.geom_bodyid[g]) in bodies and ((int(m.geom_contype[g])&int(m.geom_conaffinity[table])) or (int(m.geom_contype[table])&int(m.geom_conaffinity[g])))]
assert 1<=len(geoms)<=128
limits=m.jnt_range[m.dof_jntid[av]];pads=[m.geom(n).id for n in core.PADS]
indices=sorted(set(int(i) for i in np.linspace(0,len(motion.qpos)-1,6)))
extra=sorted(set([common_frame,max(0,common_frame-5),min(len(motion.qpos)-1,common_frame+5)])-set(indices))
seeds=[('actual_arm',None,d.qpos[aq].copy())]+[('uniform',i,motion.qpos[i,29:36].copy()) for i in indices]+[('selected_or_neighbor',i,motion.qpos[i,29:36].copy()) for i in extra]
assert len(seeds)<=10
observed=[];original=native_branch.validate_candidates
def capture(rows):
 try:return original(rows)
 finally:observed.extend(copy.deepcopy(rows))
native_branch.validate_candidates=capture
try:native_branch.select_native_branch(m,d,aq,av,hq,hand,target,R,motion.qpos[:,29:36],common,opponent,ik,pinch_center)
except ValueError:pass
finally:native_branch.validate_candidates=original
assert len(observed)==7
answers=[]
for preload in [.0005,.0015]:
 for label,index,seed in seeds:
  f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[hq]=hand;q=seed.copy()
  for _ in range(4):q=ik(m,f,aq,av,target,np.eye(3),q,seed,0.,True,True,True,R,opponent)
  f.qpos[aq]=q;mujoco.mj_forward(m,f)
  cap=float(np.linalg.norm(pinch_center(m,f,True,R,opponent)-target));spread=float(np.ptp(f.geom_xpos[pads,2]))
  hs=AdaptiveHand(m,opponent,preload,.015);hs.solve(f,target,R,hand,f.geom_xpos[pads[opponent]]-f.geom_xpos[pads[0]])
  f.qpos[hq]=core.OPEN;mujoco.mj_forward(m,f)
  row=dict(seed_label=label,source_frame=index,body_q=q.tolist(),capture_error_m=cap,pad_spread_m=spread,
   minimum_arm_limit_margin_rad=float(np.min(np.minimum(q-limits[:,0],limits[:,1]-q))),
   open_robot_table_clearance_m=min(float(mujoco.mj_geomDistance(m,f,g,table,.2,None)) for g in geoms),
   finger_replan_error_m=hs.last['max_pad_target_error_m'],native_pose_deviation_rad=float(np.linalg.norm(q-common)))
  try:original([row])
  except ValueError:pass
  row['preload_mm']=preload*1000;row['hand_diagnostic']=hs.last
  row['failed_filters']=[k for k,v in [('capture1mm',cap>.001),('flat2mm',spread>.002),('margin20mrad',row['minimum_arm_limit_margin_rad']<.02),('table10mm',row['open_robot_table_clearance_m']<.01),('hand1.5mm',row['finger_replan_error_m']>.0015)] if v]
  answers.append(row)
assert len(answers)<=20
metrics=['capture_error_m','pad_spread_m','minimum_arm_limit_margin_rad','open_robot_table_clearance_m','finger_replan_error_m','native_pose_deviation_rad']
for old,new in zip(observed,answers[:7]):
 assert old['source_frame']==new['source_frame'] and np.array_equal(old['body_q'],new['body_q'])
 assert all(old[k]==new[k] for k in metrics),'Uniform protocol not reproduced exactly'
diagnostic_stamp=copy.deepcopy(stamp)
diagnostic_stamp.update(mujoco_version=mujoco.__version__,sys_executable=sys.executable,
 python_version=platform.python_version(),diagnostic_sha256=sha(__file__),
 scene_origin='Existing scene loaded read-only; original generator fingerprint retained')
for module in ['native_branch','adaptive_hand','finger_clearance','sonic_grasp']:
 diagnostic_stamp['library_sha'][module]=sha(root/(module+'.py'))
answer=dict(physical_steps=0,runtime_stamp=diagnostic_stamp,source_episode_runtime_stamp=stamp,source_episode=a.episode,
 result_sha256=sha(folder/'result.json'),trajectory_sha256=sha(folder/'trajectory.npz'),script_sha256=sha(__file__),
 source_sha256=sha(source),saved_time_s=saved,live_stop_time_s=r['duration_s'],saved_to_stop_gap_s=gap,
 common_source_frame=common_frame,uniform_protocol_exactly_reproduced=True,candidate_bound=20,
 evaluated=len(answers),candidates=answers,
 limitation='Approximate static saved-state diagnostic, NOT exact live rejection or dynamic execution. No mj_step, no force evidence, thresholds unchanged. Hand preload matching may affect feasibility but does not prove grasp.')
with dest.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k not in ['runtime_stamp','candidates']},indent=2))
print(json.dumps([dict(frame=x['source_frame'],preload=x['preload_mm'],hand_error_mm=1000*x['finger_replan_error_m'],failed=x['failed_filters']) for x in answers],indent=2))
