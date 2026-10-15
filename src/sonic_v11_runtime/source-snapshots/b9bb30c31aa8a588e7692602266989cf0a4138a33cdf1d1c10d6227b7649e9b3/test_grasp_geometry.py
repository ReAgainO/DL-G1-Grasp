import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s,source_physics_core as core
from grasp_geometry import contact_frame
root=Path(__file__).resolve().parent;out=root/'out/grasp-surface-tests.json';assert not out.exists()
m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));d=mujoco.MjData(m)
ids=m.actuator_trnid[:29,0];aq=m.jnt_qposadr[ids[22:29]];av=m.jnt_dofadr[ids[22:29]];qa=m.jnt_qposadr[ids]
hq=m.jnt_qposadr[m.actuator_trnid[36:43,0]];d.qpos[:3]=[0,0,.74];d.qpos[3:7]=[1,0,0,0];d.qpos[qa]=s.DEFAULT_ANGLES;hand=core.CLOSED.copy();hand[2]=-.88;d.qpos[hq]=hand
seeds=json.loads((root/'out/pinch-feasibility.json').read_text())['records'];worst=0.;tests=0
for seed in [r for r in seeds if r['feasible']]:
 d.qpos[aq]=seed['q'];base=d.qpos[aq].copy();mujoco.mj_forward(m,d)
 for theta in [.1,.35]:
  R=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1]])
  p,J=contact_frame(m,d,R,av);fd=np.zeros_like(J)
  for j in range(7):
   d.qpos[aq]=base;d.qpos[aq[j]]+=1e-6;mujoco.mj_forward(m,d);plus=contact_frame(m,d,R)
   d.qpos[aq]=base;d.qpos[aq[j]]-=1e-6;mujoco.mj_forward(m,d);minus=contact_frame(m,d,R);fd[:,j]=(plus-minus)/2e-6
  d.qpos[aq]=base;mujoco.mj_forward(m,d);err=float(abs(fd-J).max());worst=max(worst,err);assert err<1e-6;tests+=1
  a,b=[d.geom_xpos[m.geom(n).id] for n in core.PADS[:2]];n=(b-a)/np.linalg.norm(b-a)
  assert abs(np.linalg.norm(b-p)-(.0175*np.sum(abs(R.T@n))+m.geom_size[m.geom(core.PADS[1]).id,0]-.0005))<1e-12;tests+=1
r=dict(physical_steps=0,pass_count=tests,max_analytic_vs_finite_difference_error=worst,tests='5 feasible branch poses x2 cube orientations x(Jacobian check + surface-distance identity)')
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
