from pathlib import Path
import json,numpy as np,mujoco
r=Path(__file__).resolve().parent;m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial26/scene.xml'));d=mujoco.MjData(m)
res={}
for n in ['physical_right_hand_thumb_2_link','physical_right_hand_middle_1_link','physical_right_hand_index_1_link','red_cube_geom','table_top']:
 g=m.geom(n).id;res[n]=dict(condim=int(m.geom_condim[g]),friction=m.geom_friction[g].tolist(),priority=int(m.geom_priority[g]),solref=m.geom_solref[g].tolist(),solimp=m.geom_solimp[g].tolist(),geomtype=str(m.geom_type[g]))
res['cube_mass']=float(m.body_mass[m.body('red_cube').id]);res['solver']=int(m.opt.solver);res['cone']=int(m.opt.cone);res['enableflags']=int(m.opt.enableflags)
(r/'out/contact_params26.json').write_text(json.dumps(res,indent=2));print(json.dumps(res),flush=True)
