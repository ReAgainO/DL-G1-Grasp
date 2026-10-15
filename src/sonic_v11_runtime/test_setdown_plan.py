"""Zero-integration tests of task-reference table-return continuity."""
import hashlib
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
from setdown_plan import SetdownPlan

root=Path(__file__).resolve().parent;out=root/'out/setdown-plan-tests';out.mkdir()
start=np.array([.277,-.07,1.09]);goal=np.array([.34,-.07,.939])
before=[start.copy(),goal.copy()];plan=SetdownPlan(start,goal)
checks=[]
def check(label,condition):
    assert condition,label
    checks.append(label)
q0,v0,a0=plan.evaluate(0);q1,v1,a1=plan.evaluate(8)
check('exact_start',np.array_equal(q0,start))
check('end_within_roundoff',np.allclose(q1,goal,atol=1e-15))
check('C2_rest_boundary_conditions',not np.any(np.r_[v0,a0,v1,a1]))
samples=[plan.evaluate(t) for t in np.linspace(0,8,8001)]
q=np.array([x[0] for x in samples]);v=np.array([x[1] for x in samples]);acc=np.array([x[2] for x in samples])
check('finite_bounded_samples',np.isfinite(np.r_[q.ravel(),v.ravel(),acc.ravel()]).all())
check('x_moves_into_table_monotonically',(np.diff(q[:,0])>=-1e-14).all())
check('z_descends_monotonically',(np.diff(q[:,2])<=1e-14).all())
check('y_unchanged',np.all(q[:,1]==start[1]))
audit=plan.audit()
check('analytic_speed_bound',np.linalg.norm(v,axis=1).max()<=audit['speed_bound_m_s']+1e-12)
check('analytic_acceleration_bound',np.linalg.norm(acc,axis=1).max()<=audit['acceleration_bound_m_s2']+1e-12)
check('input_endpoints_not_modified',np.array_equal(start,before[0]) and np.array_equal(goal,before[1]))
for name,x,y,duration in [('nan',[np.nan,0,0],goal,8),('shape',[0,0],goal,8),('short',start,goal,5),('infinite',start,goal,np.inf)]:
    rejected=False
    try:SetdownPlan(x,y,duration)
    except ValueError:rejected=True
    check('reject_'+name,rejected)
check('outside_clock_holds_rest_endpoints',np.array_equal(plan.evaluate(-1)[0],start) and np.allclose(plan.evaluate(9)[0],goal) and not np.any(plan.evaluate(9)[1]))
episode=root/'out/w5_fingergain3_free327';r=json.loads((episode/'result.json').read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
answer=dict(runtime_stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    dt=.002,model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=sha(__file__),library_sha={'setdown_plan':sha(root/'setdown_plan.py')}),
    physical_steps=0,passed=True,checks=checks,audit=audit,
    reference_model_only=True,limitations='Mathematical task-reference tests, not physical placing success or real-robot safety.')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
