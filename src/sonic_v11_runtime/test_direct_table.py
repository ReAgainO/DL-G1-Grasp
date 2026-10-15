import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
from sonic_grasp import scene_and_cal
root=Path(__file__).resolve().parent;out=root/'out/direct-table-preflight';out.mkdir()
path,*_=scene_and_cal(root,out,True,True);m=mujoco.MjModel.from_xml_path(str(path));d=mujoco.MjData(m);mujoco.mj_forward(m,d)
assert m.nq==57 and m.nu==43 and m.neq==1
assert m.eq_obj1id[0]==m.body('pelvis').id and m.eq_obj2id[0]==0
assert m.body('red_cube').jntnum==1 and m.jnt_type[m.body('red_cube').jntadr]==mujoco.mjtJoint.mjJNT_FREE
table=m.geom('table_top').id;cube=m.geom('red_cube_geom').id
height=d.geom_xpos[table,2]+m.geom_size[table,2];bottom=d.geom_xpos[cube,2]-m.geom_size[cube,2]
assert abs(height-.757)<1e-12 and abs(bottom-height)<1e-12
assert m.geom_contype[cube] and m.geom_conaffinity[cube]
assert not d.qfrc_applied.any() and not d.xfrc_applied.any()
r=dict(physical_steps=0,pass_count=6,tests=['body dimensions preserved','only pelvis-world fixture','cube retains free joint','same initial cube height directly on table','cube collisions retained','no applied external force'],table_top_z_m=float(height),cube_bottom_z_m=float(bottom),table_front_x_m=float(d.geom_xpos[table,0]-m.geom_size[table,0]),source_sha=s.sha(root/'sonic_grasp.py'),scene_sha=s.sha(path))
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
