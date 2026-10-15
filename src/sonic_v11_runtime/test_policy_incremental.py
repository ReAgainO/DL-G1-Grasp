import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s,source_physics_core as core
from policy_reference import PolicyReference,features
root=Path(__file__).resolve().parent;out=root/'out/policy-incremental-tests.json';assert not out.exists()
m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m);c=s.SonicV11(m)
d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES
hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];hand=core.CLOSED.copy();hand[2]=-.88;d.qpos[hq]=hand;mujoco.mj_forward(m,d)
c.step_policy(d,np.tile(s.DEFAULT_ANGLES,(10,1)),np.zeros((10,29)),np.tile([1.,0,0,0],(10,1)))
before=(d.qpos.copy(),d.qvel.copy(),c.target.copy(),c.last_action.copy(),c.calls,{k:np.array(v).copy() for k,v in c.hist.items()})
p=PolicyReference(c);goal=s.DEFAULT_ANGLES[22:29].copy();actual=features(m,d,True);target=actual[:3]+[.02,0,.01]
answer=p.update(d,goal,goal,target,hand,True,.03,True)
assert np.allclose(p.last_diagnostic['predicted_features'],actual,atol=1e-12)
assert np.array_equal(d.qpos,before[0]) and np.array_equal(d.qvel,before[1])
assert np.array_equal(c.target,before[2]) and np.array_equal(c.last_action,before[3]) and c.calls==before[4]
assert all(np.array_equal(np.array(c.hist[k]),v) for k,v in before[5].items())
assert np.isfinite(answer).all() and abs(answer-goal).max()<=.06+1e-9
r=dict(physical_steps=0,tests=['zero motor increment FK equals actual closed-hand FK','actual robot state unchanged','SONIC target/action/count unchanged','all policy histories unchanged','bounded finite reference update'],pass_count=5,audit=p.audit())
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
