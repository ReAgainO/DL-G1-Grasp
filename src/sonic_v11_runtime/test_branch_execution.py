"""Real branch schedule/correction positive and rejection tests; zero physics."""
import numpy as np
from branch_execution import BranchExecution

count=0
def check(value):
    global count
    assert value
    count+=1

def reject(call):
    try: call()
    except ValueError: check(True)
    else: raise AssertionError('Rejected input was accepted')

q=np.zeros(7);lo=np.full(7,-2.);hi=-lo
b=BranchExecution(10,q)
check(not b.servo_enabled(15.999))
check(b.servo_enabled(16))
check(not b.observe(15,.001,.01))
check(not b.observe(16,.026,.01))
check(not b.observe(16,.001,.21))
check(b.observe(16,.001,.01))
goal=b.correction(q,q,np.arange(7)*.5,lo,hi)
check(np.isclose(abs(goal).max(),.06) and goal[-1]>0 and goal[0]==0)
check(np.allclose(b.correction(q,q,q,lo,hi),q))
edge=np.full(7,1.99)
check(np.all(b.correction(edge,q,np.ones(7),lo,hi)<=hi))
check(b.audit()['updates']==3 and not b.audit()['body_motor_target_override'])
reject(lambda:BranchExecution(10,[0]*6))
reject(lambda:BranchExecution(float('nan'),q))
reject(lambda:b.servo_enabled(9))
reject(lambda:b.correction(q,q,[float('inf')]*7,lo,hi))
reject(lambda:b.correction(q,q,q,hi,lo))
reject(lambda:b.observe(17,-.01,.01))
print(f'branch schedule, actual readiness and input-only bounded correction: {count} PASS; physical_steps=0')
