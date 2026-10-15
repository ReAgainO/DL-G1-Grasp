"""Static collision evidence, separate from signed-distance optimization."""
import json,sys
from pathlib import Path
import numpy as np,mujoco
import wholehand_side as w
R=Path(__file__).resolve().parent;out=R/'out'/sys.argv[1]
p=json.loads((out/'plan.json').read_text())
m=mujoco.MjModel.from_xml_path(str(out/'scene.xml'));d=mujoco.MjData(m)
bq=m.jnt_qposadr[m.actuator_trnid[:29,0]];hj=m.actuator_trnid[36:43,0];hq=m.jnt_qposadr[hj]
aq,av,hv,lim,idx,pads,cube,table,bones=w.setup(m,d,bq,hj,hq)
d.qpos[:7]=[0,0,.788740,1,0,0,0];d.qpos[bq]=w.sonic.DEFAULT_ANGLES;d.qpos[idx]=p['best']['q']
mujoco.mj_forward(m,d)
contacts=[]
for c in d.contact:
 if any(int(g) in list(bones)+list(pads) for g in [c.geom1,c.geom2]):
  contacts.append({'geoms':[m.geom(int(c.geom1)).name,m.geom(int(c.geom2)).name],
   'bodies':[m.body(int(m.geom_bodyid[c.geom1])).name,m.body(int(m.geom_bodyid[c.geom2])).name],'dist':float(c.dist)})
stats=[]
for g in bones:
 v=w.vertices(m,d,int(g));delta=np.abs(v-d.geom_xpos[cube])-m.geom_size[cube]
 sdf=np.linalg.norm(np.maximum(delta,0),axis=1)+np.minimum(delta.max(axis=1),0)
 stats.append({'geom':m.geom(int(g)).name,'min':v.min(axis=0).tolist(),'max':v.max(axis=0).tolist(),
 'min_vertex_cube_sdf':float(sdf.min()),'mj_distance':float(mujoco.mj_geomDistance(m,d,int(g),int(cube),.15,None))})
r={'scene':str(out/'scene.xml'),'model_sha':w.sha(out/'robot.xml'),'mujo_version':mujoco.__version__,'table_top':.725,'cube_center':d.geom_xpos[cube].tolist(),
 'bone_stats':stats,'contacts':contacts,'wrist_R':d.xmat[m.body('right_wrist_yaw_link').id].reshape(3,3).tolist(),
 'pad_errors':p['best']['pad_errors_m']}
(out/'contact_check.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
