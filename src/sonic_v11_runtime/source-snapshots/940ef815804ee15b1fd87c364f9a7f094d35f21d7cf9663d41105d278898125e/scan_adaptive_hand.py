import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s,source_physics_core as core
from adaptive_hand import AdaptiveHand
root=Path(__file__).resolve().parent;out=root/'out/adaptive-hand-scan.json';assert not out.exists()
records=[]
for name in ['w3_middle_fast','w3_discrete_inc','w3_direct_fk']:
 p=root/'out'/name;z=np.load(p/'trajectory.npz',allow_pickle=False);m=mujoco.MjModel.from_xml_path(str(p/'scene.xml'));d=mujoco.MjData(m)
 hs=AdaptiveHand(m,2);indices=np.flatnonzero(z['phase']=='CLOSE')
 for index in indices[::max(1,len(indices)//10)]:
  d.qpos[:]=z['qpos'][index];d.qvel[:]=z['qvel'][index];mujoco.mj_forward(m,d);before=d.qpos.copy();cube=m.body('red_cube').id
  seed=core.CLOSED.copy();seed[2]=-.88
  command=hs.solve(d,d.xpos[cube].copy(),d.xmat[cube].reshape(3,3),seed)
  assert np.array_equal(d.qpos,before)
  records.append(dict(episode=name,time_s=float(z['time'][index]),**hs.last))
r=dict(physical_steps=0,source_sha=s.sha(root/'adaptive_hand.py'),records=records,minimum_max_pad_error_m=min(v['max_pad_target_error_m'] for v in records))
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(physical_steps=0,min_error=r['minimum_max_pad_error_m'],samples=len(records),first_frames=[v for v in records if v['time_s']==min(w['time_s'] for w in records if w['episode']==v['episode'])]),indent=2))
