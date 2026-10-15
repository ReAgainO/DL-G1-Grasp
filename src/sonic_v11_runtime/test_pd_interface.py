import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
root=Path(__file__).resolve().parent;m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m);c=s.SonicV11(m)
d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[c.aq]=s.DEFAULT_ANGLES;d.qpos[c.aq[22:29]]+=.05;mujoco.mj_forward(m,d)
target=c.target.copy();a=c.torques(d);b=c.torques(d,2);expected=np.clip(s.KP*(target-d.qpos[c.aq])-s.KD*d.qvel[c.av],m.actuator_ctrlrange[:29,0],m.actuator_ctrlrange[:29,1])
assert np.array_equal(a,expected) and np.array_equal(a[:22],b[:22]) and not np.array_equal(a[22:],b[22:])
assert np.array_equal(c.target,target) and np.isfinite(b).all()
assert (b>=m.actuator_ctrlrange[:29,0]).all() and (b<=m.actuator_ctrlrange[:29,1]).all()
try:c.torques(d,4.1)
except ValueError:pass
else:raise AssertionError('Gain bound')
r=dict(pass_count=5,tests=['scale1 matches official PD bitwise','only right arm torques differ at scale2','SONIC decoder target unchanged','OEM torque limits respected','reject gain>4'],source_sha=s.sha(s.__file__))
p=root/'out/pd-interface-tests.json';assert not p.exists();p.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
