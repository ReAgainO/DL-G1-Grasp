"""Compare bounded refinement at existing approximate saved rejection state."""
import argparse,copy,json,platform,sys
from pathlib import Path
import mujoco,numpy as np
from branch_refinement import refine
from native_branch import validate_candidates
from sonic_grasp import ik
from motion_input import ArdyMotion
import source_physics_core as core
from wave4_records import sha
p=argparse.ArgumentParser();p.add_argument('scan');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.scan,a.output])
scan=json.loads((root/'out'/a.scan).read_text());episode=root/'out'/scan['source_episode']
assert scan['runtime_stamp']['mujoco_version']==mujoco.__version__
assert sha(episode/'result.json')==scan['result_sha256'] and sha(episode/'trajectory.npz')==scan['trajectory_sha256']
r=json.loads((episode/'result.json').read_text());m=mujoco.MjModel.from_xml_path(str(episode/'scene.xml'));d=mujoco.MjData(m)
with np.load(episode/'trajectory.npz',allow_pickle=False) as z:
 assert 2<=len(z['time'])<=2250;d.qpos[:]=z['qpos'][-1];d.qvel[:]=z['qvel'][-1]
 target=z['qpos'][0,-7:-4]+np.array([0,0,.10])
mujoco.mj_forward(m,d);R=d.xmat[m.body('red_cube').id].reshape(3,3).copy()
source=Path(r['motion_profile']['roles']['reach']['source_npz']);assert sha(source)==scan['source_sha256']
motion=ArdyMotion(source,check_csv=source.with_suffix('.csv'));j=np.array([m.joint(n).id for n in motion.joint_names[22:29]])
aq=m.jnt_qposadr[j];av=m.jnt_dofadr[j];hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]]
recipe=core.CLOSED.copy();recipe[2]=-.88;common=motion.qpos[scan['common_source_frame'],29:36]
rows=[row for row in scan['candidates'] if row['preload_mm']==1.5 and row['source_frame'] in [0,38,39]];assert len(rows)==3
results=[]
for row in rows:
 best,audit=refine(m,d,aq,av,hq,recipe,target,R,np.asarray(row['body_q']),common,2,ik,validate_candidates)
 results.append(dict(source_frame=row['source_frame'],before=row,after=best,audit=audit))
stamp=copy.deepcopy(scan['runtime_stamp']);stamp.update(sys_executable=sys.executable,python_version=platform.python_version(),diagnostic_sha256=sha(__file__))
stamp['library_sha']['branch_refinement']=sha(root/'branch_refinement.py')
answer=dict(runtime_stamp=stamp,source_scan_sha256=sha(root/'out'/a.scan),source_episode=scan['source_episode'],
 saved_to_live_gap_s=scan['saved_to_stop_gap_s'],physical_steps=0,candidates=results,
 limitation='Saved state18ms before live stop; static candidate improvement only, no dynamics/grasp proof; three sources,52 evaluations each hard maximum')
dest=root/'out'/a.output;assert dest.suffix=='.json'
with dest.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
print(json.dumps([dict(frame=r['source_frame'],before_error_mm=r['before']['finger_replan_error_m']*1000,after_error_mm=r['after']['finger_replan_error_m']*1000,feasible=r['after'].get('static_feasible'),evaluations=r['audit']['evaluations'],capture_mm=r['after']['capture_error_m']*1000,margin_mrad=r['after']['minimum_arm_limit_margin_rad']*1000) for r in results],indent=2))
