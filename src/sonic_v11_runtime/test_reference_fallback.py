"""Adversarial bounded reference replans; explicit target branch coverage."""
import hashlib,json
from pathlib import Path
import numpy as np
from reference_filter import ReferenceFilter

root=Path(__file__).resolve().parent;out=root/'out/reference-fallback-tests';out.mkdir(parents=True,exist_ok=True);assert not (out/'result.json').exists()
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)

plain=ReferenceFilter([0.],[-1.],[1.]);safe=ReferenceFilter([0.],[-1.],[1.],True)
for i in range(100):
    a=plain.step([.2]);b=safe.step([.2]);assert all(np.array_equal(x,y) for x,y in zip(a,b))
check('feasible_branch_bitwise_legacy_parity',True)
zero=ReferenceFilter([0.],[-10.],[10.],True)
try:zero.step([9.])
except RuntimeError:check('no_prior_certificate_infeasible_goal_still_stops',True)
else:raise AssertionError('Uncertified first trajectory accepted')

# The first trajectory is valid; an abrupt reversal near the upper boundary
# makes every tested replacement infeasible. Both planners receive same goals.
plain=ReferenceFilter([.98],[-1.],[1.]);safe=ReferenceFilter([.98],[-1.],[1.],True)
rng=np.random.default_rng(93);legacy_stops=0;rows=[]
for i in range(3000):
    goal=np.array([.999 if i%200<100 else -.999])
    if i%17==0:goal=np.array([rng.uniform(-1,1)])
    if not legacy_stops:
        try:plain.step(goal)
        except RuntimeError:legacy_stops+=1
    qf,vf=safe.step(goal)
    assert (qf>=-1-1e-9).all() and (qf<=1+1e-9).all() and abs(vf).max()<=.6+1e-9
    rows.append([safe.q[0],safe.v[0],safe.a[0]])
check('legacy_infeasible_replan_branch_hit',legacy_stops>0)
check('certified_continuation_branch_hit',safe.fallback_steps>0)
check('bounded_3000_step_continuation',len(rows)==3000 and safe.calls==3000)
check('C2_boundary_continuity',safe.max_boundary_jump<1e-9)
check('analytic_derivative_certificates_preserved',np.all(safe.maxima<=[.6+1e-9,1.5+1e-9,12+1e-9]))

q,v,a=rows[-1];c,T,e=safe.certified
# Force continuation to the original certified endpoint and beyond; no new
# candidate is fabricated, and lookahead must never extrapolate past T.
for _ in range(500):qf,vf=safe._continue(.02)
check('zero_velocity_endpoint_hold',abs(vf).max()==0 and abs(safe.v).max()==0 and abs(safe.a).max()==0)
check('lookahead_clamped_at_endpoint',np.max(abs(qf-qf[0]))<1e-12)

answer=dict(physical_steps=0,checks=checks,passed=True,source_sha=hashlib.sha256((root/'reference_filter.py').read_bytes()).hexdigest(),test_source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),audit=safe.audit(),legacy_stops=legacy_stops)
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
