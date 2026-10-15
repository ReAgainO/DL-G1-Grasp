import hashlib,json,sys
from pathlib import Path
import numpy as np,mujoco
from decoded_arm_filter import DecodedArmFilter
import sonic_v11 as s
root=Path(__file__).resolve().parent;out=root/'out/decoded-arm-filter-tests';out.mkdir()
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)
f=DecodedArmFilter(np.full(7,-1.),np.full(7,1.));f.reset(np.zeros(7))
rng=np.random.default_rng(42);targets=rng.uniform(-1,1,(5000,7));seen=[]
for i in range(5000):seen.append(f.step(targets[i//10*10]))
audit=f.audit();bounds=np.array(audit['conservative_discrete_derivative_bounds']);seen=np.array(seen)
check('5000_discontinuous_targets_branch_executed',f.calls==5000)
check('range_preserved_by_convex_filter',(abs(seen)<=1+1e-12).all())
check('velocity_acceleration_jerk_discrete_bounds',np.all(f.maxima<=bounds+1e-7))
constant=np.full(7,.3)
for i in range(3000):last=f.step(constant)
check('constant_target_convergence',np.max(abs(last-constant))<1e-5)
try:f.step(np.full(7,2.))
except AssertionError:check('outside_named_limits_rejected',True)
else:raise AssertionError('range guard absent')
m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m);c=s.SonicV11(m)
d.qpos[:3]=[0,0,.78874];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES;mujoco.mj_forward(m,d)
raw=c.target.copy();action=c.last_action.copy();nominal=c.torques(d)
check('disabled_factory_torque_bitwise_parity',np.array_equal(nominal,np.clip(s.KP*(raw-d.qpos[c.aq])-s.KD*d.qvel[c.av],m.actuator_ctrlrange[:29,0],m.actuator_ctrlrange[:29,1])))
applied=raw.copy();applied[22:29]+=.01;modified=c.torques(d,actuator_target=applied)
check('only_right_arm_actuator_targets_change',np.array_equal(modified[:22],nominal[:22]) and not np.array_equal(modified[22:29],nominal[22:29]))
check('raw_sonic_action_and_target_unchanged',np.array_equal(c.target,raw) and np.array_equal(c.last_action,action))
check('original_effort_limits_preserved',(modified>=m.actuator_ctrlrange[:29,0]).all() and (modified<=m.actuator_ctrlrange[:29,1]).all())
applied[0]+=.01
try:c.torques(d,actuator_target=applied)
except ValueError:check('non_arm_target_adaptation_rejected',True)
else:raise AssertionError('non-arm guard absent')
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,dt=.002,model_sha={'scene':s.sha(root/'src/g1/scene_grasp_hand.xml'),'robot':s.sha(root/'src/g1/g1_29dof_with_hand.xml')},scene_generator_sha=s.sha(__file__),library_sha={'decoded_arm_filter':s.sha(root/'decoded_arm_filter.py'),'sonic_v11':s.sha(s.__file__),**c.model_stamp})
(out/'result.json').write_text(json.dumps(dict(runtime_stamp=stamp,physical_steps=0,checks=checks,passed=True,filter=audit),indent=2)+'\n')
print(json.dumps(dict(physical_steps=0,checks=checks,passed=True,filter=audit),indent=2))
