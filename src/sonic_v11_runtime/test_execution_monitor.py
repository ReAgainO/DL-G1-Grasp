"""Positive and negative observer branches; no physical integration."""
import json
from types import SimpleNamespace
import numpy as np
from execution_monitor import ExecutionMonitor
from neutral_pose import neutral_body

names = ['j'+str(i) for i in range(29)]
names[15],names[22] = 'left_shoulder_pitch_joint','right_shoulder_pitch_joint'
model = SimpleNamespace(actuator_trnid=np.c_[np.arange(43),np.zeros(43,dtype=int)],
    jnt_qposadr=np.arange(43),jnt_dofadr=np.arange(43),
    jnt_range=np.tile([-2.,2.],(43,1)),opt=SimpleNamespace(timestep=.002),
    joint=lambda jid:SimpleNamespace(name=names[jid]))
data = SimpleNamespace(qpos=np.zeros(43),qvel=np.zeros(43),time=.002)
tests=[]
baseline = neutral_body(model,np.zeros(29),0)
assert np.array_equal(baseline,np.zeros(29));tests.append('zero_offset_preserves_factory_reference')
offset = neutral_body(model,np.zeros(29),.1)
assert np.flatnonzero(offset).tolist() == [15,22] and np.allclose(offset[[15,22]],.1)
tests.append('only_named_shoulder_references_change')
for value in [np.nan,np.inf,.401,-.201]:
    try:neutral_body(model,np.zeros(29),value)
    except ValueError:tests.append('reject_offset_'+str(value))
    else:raise AssertionError('invalid offset accepted')
q0,v0=data.qpos.copy(),data.qvel.copy()
monitor=ExecutionMonitor(model,2.)
monitor.step(data,'SETTLE')
assert np.array_equal(data.qpos,q0) and np.array_equal(data.qvel,v0)
assert monitor.finish()['actual_arm_speed_within_limit'];tests.append('positive_actual_speed_gate')
data.qvel[27]=2.1;data.time=.004
monitor.step(data,'APPROACH')
answer=monitor.finish()
assert not answer['actual_arm_speed_within_limit']
assert answer['phases']['APPROACH']['peak_arm_joint']=='j27'
tests.append('negative_actual_speed_branch_executed')
data.qpos[0]=2.003;data.time=.006
monitor.step(data,'HOLD')
assert not monitor.finish()['actual_body_limits_within_2mrad'];tests.append('negative_actual_limit_branch_executed')
assert answer['phases']['SETTLE']['samples']==1 and answer['phases']['APPROACH']['samples']==1
tests.append('phase_samples_are_independent')
monitor.samples=45000
try:monitor.step(data,'HOLD')
except AssertionError:tests.append('negative45000_sample_bound_executed')
else:raise AssertionError('sample bound not enforced')
print(json.dumps(dict(physical_steps=0,pass_count=len(tests),tests=tests),indent=2))
