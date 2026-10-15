import json,numpy as np,mujoco
from pathlib import Path
import sonic_grasp as g,real_hand
p=Path.cwd();m=mujoco.MjModel.from_xml_path(str(p/'out/pose_plan02/scene.xml'));d=mujoco.MjData(m);a=m.actuator_trnid[:,0];qa=m.jnt_qposadr[a]
d.qpos[:3]=[0,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[qa[:29]]=g.neutral_body(m,g.s.DEFAULT_ANGLES,.2)
r=min(json.load(open(p/'out/pose_plan_candidates.json')),key=lambda x:x['score']);d.qpos[qa[22:29]]=r['arm_q'];d.qpos[qa[36:43]]=r['hand_q'];mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
cg=m.geom('red_cube_geom').id;t=m.geom('table_top').id
for bn in real_hand.DISTAL:
 gid=m.geom('physical_'+bn).id;mi=m.geom_dataid[gid];v=m.mesh_vert[m.mesh_vertadr[mi]:m.mesh_vertadr[mi]+m.mesh_vertnum[mi]];world=v@d.geom_xmat[gid].reshape(3,3).T+d.geom_xpos[gid]
 print(bn,'geomworld',d.geom_xpos[gid].tolist(),'vertexbounds',world.min(axis=0).tolist(),world.max(axis=0).tolist(),'rbound',m.geom_rbound[gid],'gdistcube',mujoco.mj_geomDistance(m,d,gid,cg,.2,None),'gdisttable',mujoco.mj_geomDistance(m,d,gid,t,.2,None))
print('table',d.geom_xpos[t],m.geom_size[t]);print('cube',d.geom_xpos[cg],m.geom_size[cg])
mujoco.mj_collision(m,d);print('NCOLLISION',d.ncon)
for c in d.contact[:d.ncon]:
 bnames=[m.body(m.geom_bodyid[x]).name for x in [c.geom1,c.geom2]]
 if cg in [c.geom1,c.geom2] or t in [c.geom1,c.geom2]:print('CONTACT',bnames,m.geom(c.geom1).name,m.geom(c.geom2).name,c.dist,c.pos.tolist())