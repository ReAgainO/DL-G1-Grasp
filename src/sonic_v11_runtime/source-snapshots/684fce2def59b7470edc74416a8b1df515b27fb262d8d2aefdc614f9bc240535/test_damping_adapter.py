import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
root=Path(__file__).resolve().parent;out=root/'out/damping-adapter-tests.json';assert not out.exists()
m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m);c=s.SonicV11(m)
d.qpos[:3]=[0,0,.78874];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES;d.qvel[c.av[22:29]]=[.2,-.4,.1,.15,-.2,.3,-.1];mujoco.mj_forward(m,d)
before=[d.qpos.copy(),d.qvel.copy(),c.target.copy(),c.last_action.copy()]
nominal=c.torques(d);expected=np.clip(s.KP*(c.target-d.qpos[c.aq])-s.KD*d.qvel[c.av],m.actuator_ctrlrange[:29,0],m.actuator_ctrlrange[:29,1]);assert np.array_equal(nominal,expected)
damped=c.torques(d,1.,0.,3.);kd=s.KD.copy();kd[22:29]*=3
expected=np.clip(s.KP*(c.target-d.qpos[c.aq])-kd*d.qvel[c.av],m.actuator_ctrlrange[:29,0],m.actuator_ctrlrange[:29,1]);assert np.array_equal(damped,expected)
assert np.array_equal(damped[:22],nominal[:22]) and not np.array_equal(damped[22:29],nominal[22:29])
assert all(np.array_equal(x,y) for x,y in zip(before,[d.qpos,d.qvel,c.target,c.last_action]))
assert (damped>=m.actuator_ctrlrange[:29,0]).all() and (damped<=m.actuator_ctrlrange[:29,1]).all()
try:c.torques(d,1.,0.,4.1)
except ValueError:pass
else:raise AssertionError('Damping bound absent')
r=dict(physical_steps=0,pass_count=6,tests=['scale1 bitwise factory parity','scale3 changes KD only','non-right-arm torques unchanged','robot state/policy targets/actions unchanged','original torque limits respected','scale>4 rejected'],source_sha=s.sha(s.__file__),audit=c.audit())
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
