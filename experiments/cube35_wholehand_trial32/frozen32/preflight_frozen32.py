from pathlib import Path
import json,numpy as np,mujoco
import normal_runner32,sonic_grasp as g,sonic_v11 as s,real_hand
from native_profile_reader32 import NativeProfile30
r=Path.cwd();o=r/'out/frozen32_preflight';o.mkdir();p,*_=g.scene_and_cal(r,o,direct_table=True,table_front=.24,cube_x=.28,cube_y=-.118,cube_edge_mm=35)
import xml.etree.ElementTree as E
tree=E.parse(p);opt=tree.getroot().find('option');opt.set('impratio','10');opt.set('solver','Newton');opt.set('tolerance','1e-10');tree.write(p,encoding='utf-8')
m=mujoco.MjModel.from_xml_path(str(p));old=mujoco.MjModel.from_xml_path(str(r.parent/'rep/out/normal_trial32/scene.xml'));fields=['body_mass','body_inertia','body_pos','body_quat','geom_type','geom_size','geom_friction','geom_contype','geom_conaffinity','geom_pos','geom_quat','jnt_range','dof_armature','dof_damping','dof_frictionloss','actuator_ctrlrange']
for f in fields:assert np.array_equal(getattr(m,f),getattr(old,f)),f
assert m.neq==0 and m.nu==43 and m.nq==57;groups,geoms=real_hand.finger_contacts(m);ctrl=s.SonicV11(m);native=NativeProfile30(r);q,p,R=native.sample([0.,5.,7.96]);assert q.shape==(3,29)
result=dict(kind='frozen relocation import/model/NN-loading preflight only; no physics execution',physical_model_fields_equal=fields,right_collision_geoms=[m.geom(gg).name for gg in geoms],sonic=ctrl.model_stamp,native_profile=native.audit(),passed=True)
(o/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
