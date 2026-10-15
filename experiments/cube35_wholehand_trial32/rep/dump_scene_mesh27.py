from pathlib import Path
import numpy as np,mujoco,json
from scipy.spatial import ConvexHull
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial27/scene.xml'));d=mujoco.MjData(m);z=np.load(r/'out/normal_trial27/trajectory.npz');idx=np.flatnonzero(z['phase']=='HOLD');d.qpos[:]=z['qpos'][idx[len(idx)//2]];mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);arrays={'qpos':d.qpos.copy()};meta=[]
boxtris=np.array([[0,1,2],[0,2,3],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]])
for gg in range(m.ngeom):
 if m.geom_contype[gg]==0 and m.geom_conaffinity[gg]==0:continue
 bn=m.body(int(m.geom_bodyid[gg])).name;gn=m.geom(gg).name;typ=int(m.geom_type[gg]);size=m.geom_size[gg]
 if typ==int(mujoco.mjtGeom.mjGEOM_MESH):
  mm=m.geom_dataid[gg];vv=m.mesh_vert[m.mesh_vertadr[mm]:m.mesh_vertadr[mm]+m.mesh_vertnum[mm]].astype(float);h=ConvexHull(vv);ff=h.simplices
 elif typ==int(mujoco.mjtGeom.mjGEOM_BOX):
  vv=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])*size;ff=boxtris
 else:continue
 ww=vv@d.geom_xmat[gg].reshape(3,3).T+d.geom_xpos[gg];arrays['v'+str(gg)]=ww;arrays['f'+str(gg)]=ff;meta.append({'id':gg,'body':bn,'name':gn,'type':typ})
arrays['meta']=np.array(json.dumps(meta));np.savez_compressed(r/'out/scene_mesh_trial27_hold.npz',**arrays);print('Collision shapes',len(meta))