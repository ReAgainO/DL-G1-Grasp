import json,numpy as np,mujoco
from pathlib import Path
from mesh_contact import FingerSurfaces
r=Path.cwd();m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial13/scene.xml'));ss=FingerSurfaces(m)
for gg,t in zip(ss.ids,ss.tris):
 u=t[:,1]-t[:,0];v=t[:,2]-t[:,0];n2=np.sum(np.cross(u,v)**2,axis=1);uu=np.sum(u*u,axis=1);vv=np.sum(v*v,axis=1);uv=np.sum(u*v,axis=1);den=uu*vv-uv*uv;print(json.dumps({'geom':m.geom(gg).name,'triangles':len(t),'min_normal_squared':float(n2.min()),'min_barycentric_den':float(den.min()),'faces_at_or_below_1e20_floor':int(((n2<=1e-20)|(den<=1e-20)).sum())}))