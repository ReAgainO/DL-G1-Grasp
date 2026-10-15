"""Saved HOLD fingertip geometry and wrist tracking; zero integration."""
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
import sonic_v11 as s
import source_physics_core as core

root=Path(__file__).resolve().parent
assert len(sys.argv)==3 and all(Path(x).name==x for x in sys.argv[1:])
folder=root/'out'/sys.argv[1];out=root/'out'/sys.argv[2];assert not out.exists()
r=json.loads((folder/'result.json').read_text())
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'))
assert s.sha(folder/'scene.xml')==r['runtime_stamp']['model_sha']['scene']
z=np.load(folder/'trajectory.npz',allow_pickle=False);assert len(z['time'])<=2250
start=next(e['time_s'] for e in r['events'] if e['phase']=='HOLD')
end=next(e['time_s'] for e in r['events'] if e['phase']=='RELEASE')
aq=m.jnt_qposadr[m.actuator_trnid[:29,0]];hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]]
cube=m.body('red_cube').id;wrist=m.body('right_wrist_yaw_link').id
padids=[m.geom(n).id for n in core.PADS]
rows=[]
for moment in [start+.02,start+.5,start+1,start+1.5,end-.25,end-.02]:
    indices=np.flatnonzero(z['phase']=='HOLD')
    i=int(indices[np.argmin(abs(z['time'][indices]-moment))])
    d=mujoco.MjData(m);d.qpos[:]=z['qpos'][i];mujoco.mj_forward(m,d)
    R=d.xmat[cube].reshape(3,3).copy()
    points=d.geom_xpos[padids].copy();local=(R.T@(points-d.xpos[cube]).T).T
    rows.append(dict(time_s=float(z['time'][i]),hold_elapsed_s=float(z['time'][i]-start),
        cube_position_m=d.xpos[cube].tolist(),cube_rotation=R.tolist(),
        wrist_position_error_m=float(np.linalg.norm(d.xpos[wrist]-z['wrist_target'][i])),
        actual_arm_q=d.qpos[aq[22:29]].tolist(),actual_finger_q=d.qpos[hq].tolist(),
        reference_finger_q=z['hand_reference'][i].tolist(),
        finger_tracking_error_max_rad=float(max(abs(d.qpos[hq]-z['hand_reference'][i]))),
        pad_centres_in_cube_frame_m=local.tolist(),finger_torque_Nm=z['actuator_ctrl'][i,36:43].tolist()))
out.mkdir();answer=dict(physical_steps=0,runtime_stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=s.sha(__file__),dt=float(m.opt.timestep),
    library_sha={'source_result':s.sha(folder/'result.json'),'trajectory':s.sha(folder/'trajectory.npz'),'sonic_v11':s.sha(root/'sonic_v11.py')}),
    pad_friction=m.geom_friction[padids].tolist(),cube_mass_kg=float(m.body_mass[cube]),
    rows=rows,warning='25Hz saved geometry/torques only; no mj_forward forces are treated as measured contact loads; not a friction-cone proof')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps({'physical_steps':0,'cube_mass_kg':answer['cube_mass_kg'],'pad_friction':answer['pad_friction'],
    'rows':[{k:row[k] for k in ['time_s','hold_elapsed_s','cube_position_m','wrist_position_error_m',
        'finger_tracking_error_max_rad','pad_centres_in_cube_frame_m','finger_torque_Nm']} for row in rows]},indent=2))
