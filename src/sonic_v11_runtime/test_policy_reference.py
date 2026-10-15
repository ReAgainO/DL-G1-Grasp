import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
import source_physics_core as core
from policy_reference import PolicyReference,features
root=Path(__file__).resolve().parent;m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m)
c=s.SonicV11(m);d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES
hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];hand=core.CLOSED.copy();hand[2]=-.88;d.qpos[hq]=hand;mujoco.mj_forward(m,d)
c.step_policy(d,np.tile(s.DEFAULT_ANGLES,(10,1)),np.zeros((10,29)),np.tile([1.,0,0,0],(10,1)))
before=dict(q=d.qpos.copy(),v=d.qvel.copy(),target=c.target.copy(),action=c.last_action.copy(),calls=c.calls,
            hist={k:np.array(v).copy() for k,v in c.hist.items()})
p=PolicyReference(c);goal=s.DEFAULT_ANGLES[22:29].copy();target=features(m,d,False)+np.array([.02,0,.01]);out=p.update(d,goal,goal,target,hand)
assert np.array_equal(d.qpos,before['q']) and np.array_equal(d.qvel,before['v'])
assert np.array_equal(c.target,before['target']) and np.array_equal(c.last_action,before['action']) and c.calls==before['calls']
assert all(np.array_equal(np.array(c.hist[k]),v) for k,v in before['hist'].items())
assert np.isfinite(out).all() and abs(out-goal).max()<=.06+1e-9 and not np.array_equal(out,goal)
r=dict(pass_count=5,tests=['actual qpos/qvel unchanged','SONIC body targets/actions unchanged','policy count unchanged','all history buffers unchanged','bounded nonzero reference suggestion'],audit=p.audit())
path=root/'out/policy-reference-tests.json';assert not path.exists();path.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
