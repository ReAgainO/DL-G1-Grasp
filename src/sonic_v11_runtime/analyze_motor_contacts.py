"""Offline analysis of recorded states; zero new physical stepping."""
import argparse,json,sys
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args()
folder=root/'out'/a.name;out=folder/'offline-motor-contacts.json';assert not out.exists()
z=np.load(folder/'trajectory.npz',allow_pickle=False);m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'));d=mujoco.MjData(m)
ids=m.actuator_trnid[:29,0];qa=m.jnt_qposadr[ids];records=[]
for phase in dict.fromkeys(z['phase']):
 indices=np.flatnonzero(z['phase']==phase);i=int(indices[-1]);d.qpos[:]=z['qpos'][i];d.qvel[:]=z['qvel'][i];mujoco.mj_forward(m,d)
 contacts=[]
 for k in range(min(200,d.ncon)):
  c=d.contact[k];bodies=[m.geom_bodyid[c.geom1],m.geom_bodyid[c.geom2]]
  contacts.append(dict(geom_names=[m.geom(c.geom1).name,m.geom(c.geom2).name],body_names=[m.body(int(b)).name for b in bodies],penetration_m=float(c.dist)))
 q=z['qpos'][indices][:,qa[22:29]];motor=z['decoded_motor_target'][indices,22:29];ref=z['body_reference'][indices,22:29]
 records.append(dict(phase=str(phase),time_s=float(z['time'][i]),motor_tracking_rms_rad=float(np.sqrt(np.mean((q-motor)**2))),
                     actual_range_rad=np.ptp(q,axis=0).tolist(),motor_target_range_rad=np.ptp(motor,axis=0).tolist(),
                     motor_target_step_max_rad=float(np.max(abs(np.diff(motor,axis=0)))) if len(indices)>1 else 0,
                     actual_arm_rad=q[-1].tolist(),decoded_motor_target_rad=motor[-1].tolist(),sonic_input_reference_rad=ref[-1].tolist(),
                     contacts_at_last_frame=contacts))
stamp=json.loads(str(z['runtime_stamp']));r=dict(source_runtime_stamp=stamp,analysis_runtime_stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
  model_sha={'scene':s.sha(folder/'scene.xml'),'robot':s.sha(folder/'g1_free_grasp.xml')},scene_generator_sha=s.sha(__file__),library_sha={'trajectory':s.sha(folder/'trajectory.npz')},dt=.002),
  physical_steps=0,warning='contacts recomputed only by mj_forward; not measured historical contact forces',records=records)
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
