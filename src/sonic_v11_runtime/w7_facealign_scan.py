"""Bounded saved-state face-alignment diagnostic; unchanged validation gates."""
import argparse,copy,json,platform,sys
from pathlib import Path
import mujoco,numpy as np
from branch_face_ik import face_ik
from adaptive_hand import AdaptiveHand
from native_branch import validate_candidates
from grasp_geometry import contact_frame
from motion_input import ArdyMotion
import source_physics_core as core
from wave4_records import sha
p=argparse.ArgumentParser();p.add_argument('scan');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.scan,a.output])
scan=json.loads((root/'out'/a.scan).read_text());episode=root/'out'/scan['source_episode']
assert scan['runtime_stamp']['mujoco_version']==mujoco.__version__ and sha(episode/'trajectory.npz')==scan['trajectory_sha256']
r=json.loads((episode/'result.json').read_text());assert sha(episode/'result.json')==scan['result_sha256']
m=mujoco.MjModel.from_xml_path(str(episode/'scene.xml'));d=mujoco.MjData(m)
with np.load(episode/'trajectory.npz',allow_pickle=False) as z:
 assert 2<=len(z['time'])<=2250;d.qpos[:]=z['qpos'][-1];d.qvel[:]=z['qvel'][-1];target=z['qpos'][0,-7:-4]+np.array([0,0,.10])
mujoco.mj_forward(m,d);R=d.xmat[m.body('red_cube').id].reshape(3,3).copy()
source=Path(r['motion_profile']['roles']['reach']['source_npz']);assert sha(source)==scan['source_sha256']
motion=ArdyMotion(source,check_csv=source.with_suffix('.csv'));j=np.array([m.joint(n).id for n in motion.joint_names[22:29]])
aq=m.jnt_qposadr[j];av=m.jnt_dofadr[j];hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];limits=m.jnt_range[j]
recipe=core.CLOSED.copy();recipe[2]=-.88;common=motion.qpos[scan['common_source_frame'],29:36]
table=m.geom('table_top').id;bodies={m.body('pelvis').id}
for body in range(1,m.nbody):
 if int(m.body_parentid[body]) in bodies:bodies.add(body)
geoms=[g for g in range(m.ngeom) if int(m.geom_bodyid[g]) in bodies and ((int(m.geom_contype[g])&int(m.geom_conaffinity[table])) or (int(m.geom_contype[table])&int(m.geom_conaffinity[g])))]
assert 1<=len(geoms)<=128;pads=[m.geom(n).id for n in core.PADS]
old=[row for row in scan['candidates'] if row['preload_mm']==.5];assert len(old)<=10
answers=[]
for row in old:
 seed=d.qpos[aq].copy() if row['source_frame'] is None else motion.qpos[row['source_frame'],29:36].copy()
 f=mujoco.MjData(m);f.qpos[:]=d.qpos;f.qpos[hq]=recipe;q=seed.copy()
 try:
  for _ in range(4):q=face_ik(m,f,aq,av,target,np.eye(3),q,seed,0.,True,True,True,R,2)
 except ValueError as error:
  answers.append(dict(source_frame=row['source_frame'],static_feasible=False,rejection=str(error),preload_mm=None))
  continue
 f.qpos[aq]=q;mujoco.mj_forward(m,f)
 cap=float(np.linalg.norm(contact_frame(m,f,R,opponent=2)-target));spread=float(np.ptp(f.geom_xpos[pads,2]))
 for preload in [.0005,.0015]:
  hs=AdaptiveHand(m,2,preload,.015);hs.solve(f,target,R,recipe,f.geom_xpos[pads[2]]-f.geom_xpos[pads[0]])
  opening=mujoco.MjData(m);opening.qpos[:]=f.qpos;opening.qpos[hq]=core.OPEN;mujoco.mj_forward(m,opening)
  answer=dict(source_frame=row['source_frame'],body_q=q.tolist(),capture_error_m=cap,pad_spread_m=spread,
   minimum_arm_limit_margin_rad=float(np.min(np.minimum(q-limits[:,0],limits[:,1]-q))),
   open_robot_table_clearance_m=min(float(mujoco.mj_geomDistance(m,opening,g,table,.2,None)) for g in geoms),
   finger_replan_error_m=hs.last['max_pad_target_error_m'],native_pose_deviation_rad=float(np.linalg.norm(q-common)),preload_mm=preload*1000,hand_plan=hs.last)
  try:validate_candidates([answer])
  except ValueError:pass
  answers.append(answer)
assert len(answers)<=20
stamp=copy.deepcopy(scan['runtime_stamp']);stamp.update(sys_executable=sys.executable,python_version=platform.python_version(),diagnostic_sha256=sha(__file__))
stamp['library_sha']['branch_face_ik']=sha(root/'branch_face_ik.py')
answer=dict(runtime_stamp=stamp,source_scan_sha256=sha(root/'out'/a.scan),physical_steps=0,saved_to_live_gap_s=scan['saved_to_stop_gap_s'],
 candidates=answers,candidate_bound=20,arm_iterations_per_seed_bound=60,hand_iterations_per_candidate_bound=35,
 limitation='Approximate saved-state FK only; source ARDY seeds plus explicit object-face yaw retargeting, not an original generated orientation or motor override; all existing static gates preserved; not dynamic grasp proof.')
dest=root/'out'/a.output;assert dest.suffix=='.json'
with dest.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
def measured(row,key):return row[key]*1000 if key in row else None
print(json.dumps([dict(frame=x['source_frame'],preload=x['preload_mm'],hand_mm=measured(x,'finger_replan_error_m'),capture_mm=measured(x,'capture_error_m'),spread_mm=measured(x,'pad_spread_m'),margin_mrad=measured(x,'minimum_arm_limit_margin_rad'),feasible=x.get('static_feasible'),rejection=x.get('rejection')) for x in answers],indent=2))
