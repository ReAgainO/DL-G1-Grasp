"""Zero-integration actuator interface and default-equivalence checks."""
import hashlib
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
import source_physics_core as core
from finger_control import finger_torques

root=Path(__file__).resolve().parent
out=root/'out/finger-controller-tests'
out.mkdir()
episode=root/'out/w5_front240_live327'
r=json.loads((episode/'result.json').read_text())
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
z=np.load(episode/'trajectory.npz',allow_pickle=False)
m=mujoco.MjModel.from_xml_path(str(episode/'scene.xml'))
j=m.actuator_trnid[36:43,0]
aq=m.jnt_qposadr[j];av=m.jnt_dofadr[j]
kp,kd=core.gains();kp=kp[core.HAND];kd=kd[core.HAND]
limits=m.actuator_ctrlrange[36:43].copy()
checks=[]
def check(label,condition):
    assert condition,label
    checks.append(label)
i=np.flatnonzero(z['phase']=='LIFT')[0]
command=z['hand_reference'][i].copy()
position=z['qpos'][i,aq].copy();velocity=z['qvel'][i,av].copy()
before=[a.copy() for a in [command,position,velocity,kp,kd,limits]]
old=np.clip(kp*(command-position)-kd*velocity,limits[:,0],limits[:,1])
new=finger_torques(command,position,velocity,kp,kd,limits,2,1.)
check('default_output_bitwise_matches_prior_PD',np.array_equal(old,new))
for opponent,inactive in [(1,[5,6]),(2,[3,4])]:
    for gain in [1.,2.,3.]:
        torque=finger_torques(command,position,velocity,kp,kd,limits,opponent,gain)
        check(f'finite_and_factory_limits_{opponent}_{gain}',np.isfinite(torque).all() and (torque>=limits[:,0]).all() and (torque<=limits[:,1]).all())
        check(f'inactive_finger_unchanged_{opponent}_{gain}',np.array_equal(torque[inactive],old[inactive]))
        if gain>1:
            check(f'gain_changes_selected_torque_{opponent}_{gain}',not np.array_equal(torque,new))
for invalid in [0.,3.01,np.nan,np.inf]:
    rejected=False
    try:finger_torques(command,position,velocity,kp,kd,limits,2,invalid)
    except ValueError:rejected=True
    check(f'invalid_gain_rejected_{invalid}',rejected)
saturated=finger_torques(command+100,position,velocity,kp,kd,limits,2,3.)
check('large_error_still_exact_factory_limits',np.array_equal(saturated,limits[:,1]))
check('input_arrays_unmodified',all(np.array_equal(a,b) for a,b in zip(before,[command,position,velocity,kp,kd,limits])))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    dt=float(m.opt.timestep),model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=sha(__file__),
    library_sha={'finger_control':sha(root/'finger_control.py'),'source_physics_core':sha(core.__file__),
        'episode':sha(episode/'result.json'),'trajectory':sha(episode/'trajectory.npz')})
answer=dict(runtime_stamp=stamp,physical_steps=0,passed=True,checks=checks,
    limitations='Actuator-interface checks only; not force regulation, grasp success, or real robot safety evidence.')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
