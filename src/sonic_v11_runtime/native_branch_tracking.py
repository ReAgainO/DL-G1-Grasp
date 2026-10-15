"""Zero-step saved actual/reference/decoded grasp-point reconstruction."""
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
import sonic_v11 as s
import source_physics_core as core
from sonic_grasp import pinch_center

root=Path(__file__).resolve().parent
assert len(sys.argv)==3 and all(Path(x).name==x for x in sys.argv[1:])
folder=root/'out'/sys.argv[1];out=root/'out'/sys.argv[2];assert not out.exists()
r=json.loads((folder/'result.json').read_text())
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'))
assert s.sha(folder/'scene.xml')==r['runtime_stamp']['model_sha']['scene']
z=np.load(folder/'trajectory.npz',allow_pickle=False);assert len(z['time'])<=2250
qa=m.jnt_qposadr[m.actuator_trnid[:29,0]];va=m.jnt_dofadr[m.actuator_trnid[:29,0]]
hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]]
cube=m.body('red_cube').id;wrist=m.body('right_wrist_yaw_link').id
hand=core.CLOSED.copy();hand[2]=-.88
audit=r['post_clearance_native_branch'];desired=np.asarray(audit['selected']['body_q'])
target=np.asarray(audit['target_closed_pad_surface_m'])
assert r['kinematic_outer_servo']['motor_target_override'] is False
rows=[]
for moment in [audit['selected_time_s'],audit['selected_time_s']+3,audit['selected_time_s']+6,float(z['time'][-1])]:
    i=int(np.argmin(abs(z['time']-moment)));d=mujoco.MjData(m);d.qpos[:]=z['qpos'][i]
    d.qpos[hq]=hand;mujoco.mj_forward(m,d);R=d.xmat[cube].reshape(3,3).copy()
    row=dict(time_s=float(z['time'][i]),actual_arm_q=d.qpos[qa[22:29]].tolist(),actual_arm_speed_rad_s=float(max(abs(z['qvel'][i,va[22:29]]))),
        base_position_m=d.qpos[:3].tolist(),branch_target_m=target.tolist())
    for key,q in [('actual',d.qpos[qa[22:29]].copy()),('reference',z['body_reference'][i,22:29]),('decoded',z['decoded_motor_target'][i,22:29]),('static_selected',desired)]:
        d.qpos[qa[22:29]]=q;mujoco.mj_forward(m,d)
        point=pinch_center(m,d,True,R,2)
        row[key]=dict(arm_q=q.tolist(),wrist_xyz_m=d.xpos[wrist].tolist(),closed_recipe_point_m=point.tolist(),capture_error_m=float(np.linalg.norm(point-target)))
    row['actual_decoded_joint_error_max_rad']=float(max(abs(np.asarray(row['actual']['arm_q'])-row['decoded']['arm_q'])))
    rows.append(row)
out.mkdir();answer=dict(physical_steps=0,runtime_stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=s.sha(__file__),dt=float(m.opt.timestep),library_sha={'source_result':s.sha(folder/'result.json'),'trajectory':s.sha(folder/'trajectory.npz'),'sonic_v11':s.sha(root/'sonic_v11.py')}),
    branch=audit,rows=rows,warning='Hypothetical closed hand and static FK only, not force/contact or a realizable decoded pose')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps({'physical_steps':0,'rows':rows},indent=2))
