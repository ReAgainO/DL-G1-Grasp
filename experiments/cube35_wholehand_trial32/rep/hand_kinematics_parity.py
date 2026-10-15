import numpy as np,mujoco,json
from pathlib import Path
from mesh_contact_v2 import FingerSurfaces
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial14/scene.xml'));z=np.load(r/'out/normal_trial14/trajectory.npz');a=mujoco.MjData(m);b=mujoco.MjData(m);a.qpos[:]=z['qpos'][-1];b.qpos[:]=a.qpos;mujoco.mj_forward(m,a);mujoco.mj_kinematics(m,b);mujoco.mj_comPos(m,b);ss=FingerSurfaces(m);cube=m.body('red_cube').id;cg=m.geom('red_cube_geom').id;p1=ss.points(a,a.xpos[cube],a.xmat[cube].reshape(3,3),m.geom_size[cg,0]);p2=ss.points(b,b.xpos[cube],b.xmat[cube].reshape(3,3),m.geom_size[cg,0]);je=0
for pt,gg in zip(p1,ss.ids):
 j1=np.zeros((3,m.nv));j2=j1.copy();mujoco.mj_jac(m,a,j1,None,pt,int(m.geom_bodyid[gg]));mujoco.mj_jac(m,b,j2,None,pt,int(m.geom_bodyid[gg]));je=max(je,float(abs(j1-j2).max()))
res={'surface_world_point_max_error':float(abs(p1-p2).max()),'point_jacobian_max_error':je};print(json.dumps(res));assert max(res.values())<1e-10;(r/'out/hand_kinematics_parity15.json').write_text(json.dumps(res,indent=2))