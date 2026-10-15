"""Structure and support tests for labelled table placement; no physics steps."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import mujoco
import numpy as np
import sonic_v11 as s
from sonic_grasp import scene_and_cal
from table_placement import place_direct_table

root = Path(__file__).resolve().parent
out = root/'out/table-placement-tests-v2'
out.mkdir()
checks = []
def check(label, condition):
    assert condition, label
    checks.append(label)
scenes=[]
models=[]
for name,front,fixture in [('canonical',.23,True),('free-old',.23,False),('free-new',.24,False)]:
    dest=out/name
    dest.mkdir()
    scene,*_=scene_and_cal(root,dest,fixture,True,table_front=front)
    scenes.append(scene)
    models.append(mujoco.MjModel.from_xml_path(str(scene)))
old=json.loads((root/'out/w5_matched_on327/result.json').read_text())
check('default_scene_bitwise_same_as_matched_positive',s.sha(scenes[0])==old['runtime_stamp']['model_sha']['scene'])
check('default_robot_bitwise_same_as_matched_positive',s.sha(scenes[0].parent/'g1_free_grasp.xml')==old['runtime_stamp']['model_sha']['robot'])
baseline,new=models[1:]
check('free_robot_dimensions_unchanged',new.nq==baseline.nq==57 and new.nu==baseline.nu==43 and new.neq==baseline.neq==0)
check('robot_XML_not_changed_by_table_front',s.sha(scenes[1].parent/'g1_free_grasp.xml')==s.sha(scenes[2].parent/'g1_free_grasp.xml'))
check('collision_masks_unchanged',np.array_equal(new.geom_contype,baseline.geom_contype) and np.array_equal(new.geom_conaffinity,baseline.geom_conaffinity))
table_body=new.body('grasp_table').id
physical_bodies=np.arange(new.nbody)!=table_body
check('robot_cube_masses_inertias_and_all_friction_unchanged',np.array_equal(new.body_mass[physical_bodies],baseline.body_mass[physical_bodies]) and np.array_equal(new.body_inertia[physical_bodies],baseline.body_inertia[physical_bodies]) and np.array_equal(new.geom_friction,baseline.geom_friction))
check('table_is_static_world_child_without_joints',new.body_parentid[table_body]==0 and new.body_jntnum[table_body]==0)
d0=mujoco.MjData(baseline)
d1=mujoco.MjData(new)
mujoco.mj_forward(baseline,d0)
mujoco.mj_forward(new,d1)
check('same_generalized_mass_matrix_at_identical_state',np.array_equal(d0.qM,d1.qM))
d=mujoco.MjData(new)
mujoco.mj_forward(new,d)
table=new.geom('table_top').id
cube=new.geom('red_cube_geom').id
top=float(d.geom_xpos[table,2]+new.geom_size[table,2])
front=float(d.geom_xpos[table,0]-new.geom_size[table,0])
back=float(d.geom_xpos[table,0]+new.geom_size[table,0])
edge=float(d.geom_xpos[cube,0]-new.geom_size[cube,0]-front)
check('same_initial_height_and_back_edge',abs(top-.757)<1e-12 and abs(back-.87)<1e-12)
check('new_front240mm_and_full_cube_footprint_supported',abs(front-.24)<1e-12 and abs(edge-.0095)<1e-12)
check('cube_freejoint_not_welded_or_teleported',new.jnt_type[new.body('red_cube').jntadr].item()==mujoco.mjtJoint.mjJNT_FREE and np.array_equal(new.qpos0,baseline.qpos0))
check('no_external_applied_forces',not d.qfrc_applied.any() and not d.xfrc_applied.any())
for invalid in [.22,.246,float('nan')]:
    element=ET.Element('geom',pos='unchanged')
    try:
        place_direct_table(element,invalid)
    except ValueError:
        check('invalid_front_rejected_'+str(invalid),element.get('pos')=='unchanged')
    else:
        raise AssertionError('Invalid front accepted')
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,
    python_version=sys.version,dt=float(new.opt.timestep),
    model_sha={'scene':s.sha(scenes[2]),'robot':s.sha(scenes[2].parent/'g1_free_grasp.xml')},
    scene_generator_sha=s.sha(__file__),library_sha={'sonic_grasp':s.sha(root/'sonic_grasp.py'),
    'table_placement':s.sha(root/'table_placement.py'),'source_physics_core':s.sha(root/'source_physics_core.py')})
answer=dict(runtime_stamp=stamp,physical_steps=0,passed=True,checks=checks,
    static_table_compiled_mass_kg={'before':float(baseline.body_mass[table_body]),'after':float(new.body_mass[table_body])},
    static_table_compiled_inertia_kg_m2={'before':baseline.body_inertia[table_body].tolist(),'after':new.body_inertia[table_body].tolist()},
    static_inertia_note='Compiler infers table mass/inertia from changed tabletop geometry. This static world child has no joints; robot/cube inertias and generalized mass matrix are unchanged. Earlier all-body equality test failed and is preserved.',
    cube_front_support_margin_m=edge,scope='Geometry/structure only. Dynamic contact, grasp and balance must be physically tested.')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
