import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
root=Path(__file__).resolve().parent;out=root/'out/gravity-adapter-tests.json';assert not out.exists()
m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m);c=s.SonicV11(m)
d.qpos[:3]=[0,0,.78874];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES;d.qpos[c.aq[22:29]]=[-1,-.6,1,.4,-.3,.2,1];mujoco.mj_forward(m,d)
before=(d.qpos.copy(),d.qvel.copy(),d.qfrc_applied.copy(),d.xfrc_applied.copy(),c.target.copy(),c.last_action.copy())
zero=c.torques(d,1.,0.);expected=np.clip(s.KP*(c.target-d.qpos[c.aq])-s.KD*d.qvel[c.av],m.actuator_ctrlrange[:29,0],m.actuator_ctrlrange[:29,1]);assert np.array_equal(zero,expected)
c.torque_steps=0;full=c.torques(d,1.,1.);g=d.qfrc_bias[c.av[22:29]];expected2=expected.copy();raw=s.KP*(c.target-d.qpos[c.aq])-s.KD*d.qvel[c.av];raw[22:29]+=g
expected2=np.clip(raw,m.actuator_ctrlrange[:29,0],m.actuator_ctrlrange[:29,1]);assert np.allclose(full,expected2,atol=1e-12)
assert np.array_equal(full[:22],zero[:22])
assert all(np.array_equal(x,y) for x,y in zip(before,[d.qpos,d.qvel,d.qfrc_applied,d.xfrc_applied,c.target,c.last_action]))
assert (full>=m.actuator_ctrlrange[:29,0]).all() and (full<=m.actuator_ctrlrange[:29,1]).all()
try:c.torques(d,1.,1.1)
except ValueError:pass
else:raise AssertionError('No scale bound')
r=dict(physical_steps=0,pass_count=6,tests=['FF0 bitwise factory PD parity','FF1 equals static model gravity plus PD then original limits','non-right-arm channels unchanged','actual state/external forces/policy targets/actions unchanged','original effort limits preserved','reject scale outside0..1'],right_arm_gravity_Nm=g.tolist(),audit=c.audit())
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
