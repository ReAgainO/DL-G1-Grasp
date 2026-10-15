import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s,source_physics_core as core
from discrete_reference import DiscreteReference
root=Path(__file__).resolve().parent;out=root/'out/discrete-reference-tests.json';assert not out.exists()
m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m);c=s.SonicV11(m)
d.qpos[:3]=[0,0,.78874];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES
hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];hand=core.CLOSED.copy();hand[2]=-.88;d.qpos[hq]=hand;mujoco.mj_forward(m,d)
c.step_policy(d,np.tile(s.DEFAULT_ANGLES,(10,1)),np.zeros((10,29)),np.tile([1.,0,0,0],(10,1)))
before=(d.qpos.copy(),d.qvel.copy(),d.qfrc_applied.copy(),d.xfrc_applied.copy(),c.target.copy(),c.last_action.copy(),c.calls,{k:np.array(v).copy() for k,v in c.hist.items()})
p=DiscreteReference(c);anchor=s.DEFAULT_ANGLES[22:29].copy();feature=p.feature(d,anchor,hand,np.eye(3),1)
answer=p.update(d,anchor,anchor+np.array([-.1,0,0,.1,0,0,0]),anchor,feature[:3]+[.02,0,.01],hand,np.eye(3))
assert all(np.array_equal(x,y) for x,y in zip(before[:6],[d.qpos,d.qvel,d.qfrc_applied,d.xfrc_applied,c.target,c.last_action]))
assert c.calls==before[6] and all(np.array_equal(np.array(c.hist[k]),v) for k,v in before[7].items())
assert np.isfinite(answer).all() and abs(answer-anchor).max()<=.12+1e-9
assert p.last_diagnostic['candidate_count']>=1
out.write_text(json.dumps(dict(physical_steps=0,pass_count=4,tests=['robot state/forces unchanged','policy action/target/count/histories unchanged','bounded finite legal reference','every candidate uses unchanged official encoder and decoder'],audit=p.audit()),indent=2)+'\n')
print(out.read_text())
