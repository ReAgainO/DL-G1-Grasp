import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
from adaptive_hand import AdaptiveHand
import source_physics_core as core
root=Path(__file__).resolve().parent;out=root/'out/adaptive-hand-tests.json';assert not out.exists()
p=root/'out/w3_direct_fk';m=mujoco.MjModel.from_xml_path(str(p/'scene.xml'));d=mujoco.MjData(m);z=np.load(p/'trajectory.npz',allow_pickle=False)
index=np.flatnonzero(z['phase']=='CLOSE')[0];d.qpos[:]=z['qpos'][index];d.qvel[:]=z['qvel'][index];mujoco.mj_forward(m,d)
before=[d.qpos.copy(),d.qvel.copy(),d.ctrl.copy(),d.qfrc_applied.copy(),d.xfrc_applied.copy()];hs=AdaptiveHand(m,2);cube=m.body('red_cube').id
seed=core.CLOSED.copy();seed[2]=-.88;command=hs.solve(d,d.xpos[cube].copy(),d.xmat[cube].reshape(3,3),seed)
assert all(np.array_equal(x,y) for x,y in zip(before,[d.qpos,d.qvel,d.ctrl,d.qfrc_applied,d.xfrc_applied]))
assert np.isfinite(command).all() and (command>=hs.lo).all() and (command<=hs.hi).all()
assert np.array_equal(command[3:5],seed[3:5])
targets=np.array(hs.last['target_points_m']);R=d.xmat[cube].reshape(3,3);local=(targets-d.xpos[cube])@R;axis=hs.last['opposing_cube_axis']
assert local[0,axis]*local[1,axis]<0
r=dict(physical_steps=0,pass_count=4,tests=['all actual state/control/forces unchanged','finite commands inside original finger limits','non-opposing index joints unchanged','target contact faces opposed'],source_sha=s.sha(root/'adaptive_hand.py'),last=hs.last)
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
