"""Finite analytic and sampled tests of the task-level C2 progress adaptation."""
import hashlib
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
from lift_progress import LiftProgress

root=Path(__file__).resolve().parent
out=root/'out/lift-progress-tests'
out.mkdir()
checks=[]
def check(label,condition):
    assert condition,label
    checks.append(label)
curve=LiftProgress(np.array([0,0,.1,.9,1,1]),8,4)
ts=np.linspace(0,8,8001)
samples=np.array([curve.evaluate(t) for t in ts])
check('finite_with_explicit_8001_sample_bound',np.isfinite(samples).all())
check('zero_position_velocity_acceleration_at_start',curve.evaluate(0)==(0.,0.,0.))
check('one_position_zero_velocity_acceleration_at_end',curve.evaluate(8)==(1.,0.,0.))
check('monotone_progress',np.diff(samples[:,0]).min()>=-1e-14)
check('normalized_range',samples[:,0].min()>=0 and samples[:,0].max()<=1)
audit=curve.audit()
check('analytic_velocity_bound',abs(samples[:,1]).max()<=audit['progress_velocity_bound_per_s']+1e-12)
check('analytic_acceleration_bound',abs(samples[:,2]).max()<=audit['progress_acceleration_bound_per_s2']+1e-12)
check('derivative_consistency',np.max(abs(np.gradient(samples[:,0],.001)[1:-1]-samples[1:-1,1]))<1e-6)
jump=0.
for endpoint in np.r_[curve.starts,curve.starts+curve.window_s]:
    jump=max(jump,float(np.max(abs(np.asarray(curve.evaluate(endpoint+1e-8))-curve.evaluate(endpoint-1e-8)))))
check('C2_boundaries_numerically_continuous',jump<1e-7)
early=LiftProgress([0,1,1,1,1],8,4)
late=LiftProgress([0,0,0,0,1],8,4)
check('native_distribution_changes_output',early.evaluate(3)[0]>late.evaluate(3)[0]+.2)
for label,progress,window in [('decreasing',[0,.8,.2,1],4),('not_normalized',[.1,1],4),('nan',[0,np.nan,1],4),('window_discards_source',[0,1],8),('window_too_short',[0,1],1)]:
    rejected=False
    try:LiftProgress(progress,8,window)
    except ValueError:rejected=True
    check('reject_'+label,rejected)
check('outside_clock_holds_C2_endpoints',curve.evaluate(-1)==(0.,0.,0.) and curve.evaluate(9)==(1.,0.,0.))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
episode=root/'out/w5_front240_live327'
r=json.loads((episode/'result.json').read_text())
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    dt=.002,model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=sha(__file__),
    library_sha={'lift_progress':sha(root/'lift_progress.py')})
answer=dict(runtime_stamp=stamp,physical_steps=0,passed=True,checks=checks,audit=audit,boundary_probe_max_difference=jump,
    limitations='Scalar mathematical tests only; no physical grasp or actual joint smoothness claim.')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
