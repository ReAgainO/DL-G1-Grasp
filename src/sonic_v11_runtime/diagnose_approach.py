"""Saved-pose FK versus reference/motor FK; no physical integration."""
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
from sonic_v11 import sha

root=Path(__file__).resolve().parent
assert len(sys.argv)==3 and all(Path(x).name==x for x in sys.argv[1:])
episode=root/'out'/sys.argv[1];out=root/'out'/sys.argv[2]
assert not out.exists()
r=json.loads((episode/'result.json').read_text())
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
m=mujoco.MjModel.from_xml_path(str(episode/'scene.xml'))
assert sha(episode/'scene.xml')==r['runtime_stamp']['model_sha']['scene']
z=np.load(episode/'trajectory.npz',allow_pickle=False)
assert len(z['time'])<=2250
d=mujoco.MjData(m);fk=mujoco.MjData(m)
aq=m.jnt_qposadr[m.actuator_trnid[:29,0]];av=m.jnt_dofadr[m.actuator_trnid[:29,0]]
wrist=m.body('right_wrist_yaw_link').id
rows=[]
for i,(pose,phase) in enumerate(zip(z['qpos'],z['phase'])):
    if str(phase) not in ['SETTLE','APPROACH']:
        continue
    d.qpos[:]=pose;mujoco.mj_forward(m,d)
    reference=z['body_reference'][i]
    fk.qpos[:]=pose;fk.qpos[aq]=reference;mujoco.mj_forward(m,fk)
    reference_wrist=fk.xpos[wrist].copy()
    fk.qpos[aq]=z['decoded_motor_target'][i];mujoco.mj_forward(m,fk)
    rows.append(dict(time_s=float(z['time'][i]),phase=str(phase),actual_wrist_xyz_m=d.xpos[wrist].tolist(),
        reference_wrist_xyz_m=reference_wrist.tolist(),motor_wrist_xyz_m=fk.xpos[wrist].tolist(),
        requested_wrist_target_m=z['wrist_target'][i].tolist() if np.isfinite(z['wrist_target'][i]).all() else None))
assert rows
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=sha(__file__),dt=float(m.opt.timestep),
    library_sha={'result':sha(episode/'result.json'),'trajectory':sha(episode/'trajectory.npz'),'sonic_v11':sha(root/'sonic_v11.py')})
answer=dict(runtime_stamp=stamp,source_episode_runtime_stamp=r['runtime_stamp'],physical_steps=0,
    sample_hz=25,maximum_actual_wrist_z_m=max(x['actual_wrist_xyz_m'][2] for x in rows),
    maximum_reference_wrist_z_m=max(x['reference_wrist_xyz_m'][2] for x in rows),
    maximum_motor_wrist_z_m=max(x['motor_wrist_xyz_m'][2] for x in rows),last=rows[-1],
    warning='FK reconstruction from25Hz samples, not physics forces, 500Hz maxima or a realizable hypothetical motor pose',rows=rows)
out.mkdir();(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k not in ['runtime_stamp','source_episode_runtime_stamp','rows']},indent=2))
