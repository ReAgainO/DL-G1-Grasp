"""Replay static search at the LAST SAVED pose, not the unsaved live stop pose.

This is a diagnostic with zero physics steps. The saved/stop clock gap is
explicit; candidate feasibility here is not a dynamic execution certificate.
"""
import argparse
import copy
import json
from pathlib import Path
import mujoco
import numpy as np
import native_branch
import source_physics_core as core
from motion_input import ArdyMotion
from sonic_grasp import ik,pinch_center
from wave4_records import sha

p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(name).name==name and len(name)<128 for name in [a.episode,a.output])
folder=root/'out'/a.episode;dest=root/'out'/a.output;assert dest.suffix=='.json' and not dest.exists()
r=json.loads((folder/'result.json').read_text());stamp=r['runtime_stamp']
assert stamp['mujoco_version']==mujoco.__version__ and sha(folder/'scene.xml')==stamp['model_sha']['scene']
assert sha(root/'native_branch.py')==stamp['library_sha']['native_branch']
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'));d=mujoco.MjData(m)
with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
    assert 2<=len(z['time'])<=2250
    d.qpos[:]=z['qpos'][-1];d.qvel[:]=z['qvel'][-1];saved_time=float(z['time'][-1])
    initial_cube_qpos=z['qpos'][0,-7:-4].copy()
gap=r['duration_s']-saved_time;assert 0<=gap<=.041
entry=r['motion_profile']['roles']['reach'];source=Path(entry['source_npz'])
assert source.resolve().is_relative_to(root) and sha(source)==entry['source_npz_sha256']
motion=ArdyMotion(source,check_csv=source.with_suffix('.csv'))
arm_jids=np.array([m.joint(name).id for name in motion.joint_names[22:29]])
aq=m.jnt_qposadr[arm_jids];av=m.jnt_dofadr[arm_jids]
hand_ids=m.actuator_trnid[36:43,0];hq=m.jnt_qposadr[hand_ids]
wrist=m.body('right_wrist_yaw_link').id;cube=m.body('red_cube').id
geo=mujoco.MjData(m);geo.qpos[:]=d.qpos;geo.qpos[:3]=[0,0,.74];geo.qpos[3:7]=[1,0,0,0]
body_ids=np.array([m.joint(name).id for name in motion.joint_names]);bq=m.jnt_qposadr[body_ids]
xs=[]
for q in motion.qpos:
    geo.qpos[bq]=q[7:];mujoco.mj_forward(m,geo);xs.append(float(geo.xpos[wrist,0]))
frame=int(np.argmax(xs));hand=core.CLOSED.copy();hand[2]=-.88
mujoco.mj_forward(m,d);target=initial_cube_qpos+np.array([0,0,.10])
opponent=2 if r['opposing_pad']=='right_middle_fingertip' else 1
observed=[];original=native_branch.validate_candidates
def capture(rows):
    try:return original(rows)
    finally:observed.extend(copy.deepcopy(rows))
native_branch.validate_candidates=capture
error=None;selected=None
try:
    q,audit=native_branch.select_native_branch(m,d,aq,av,hq,hand,target,d.xmat[cube].reshape(3,3),
        motion.qpos[:,29:36],motion.qpos[frame,29:36],opponent,ik,pinch_center)
    selected=audit['selected']
except ValueError as exc:error=str(exc)
finally:native_branch.validate_candidates=original
assert len(observed)==7
for row in observed:
    row['failed_filters']=[key for key,failed in [
        ('capture1mm',row['capture_error_m']>.001),('flat2mm',row['pad_spread_m']>.002),
        ('arm_margin20mrad',row['minimum_arm_limit_margin_rad']<.02),
        ('open_table10mm',row['open_robot_table_clearance_m']<.01),
        ('finger_error1.5mm',row['finger_replan_error_m']>.0015)] if failed]
answer=dict(physical_steps=0,source_episode=a.episode,runtime_stamp=stamp,
    result_sha256=sha(folder/'result.json'),trajectory_sha256=sha(folder/'trajectory.npz'),
    source_sha256=sha(source),script_sha256=sha(__file__),saved_state_time_s=saved_time,
    live_stop_time_s=r['duration_s'],saved_to_stop_gap_s=gap,target_m=target.tolist(),
    common_source_frame=frame,replayed_rejection=error,replayed_selected=selected,candidates=observed,
    limitation='Approximate static replay from last saved25Hz state, NOT the exact unsaved failure state. Same filters and code; no mj_step, no force or stability evidence. Candidate reasons guide subsequent measured tests only.')
dest.write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps({key:value for key,value in answer.items() if key!='runtime_stamp'},indent=2))
