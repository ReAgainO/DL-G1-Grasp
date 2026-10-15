import json
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
from sonic_grasp import scene_and_cal
root=Path(__file__).resolve().parent;out=root/'out/dynamics-scene-tests';out.mkdir();audit=json.loads((root/'out/official-dynamics.json').read_text());records=[]
base=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'))
for passive in [False,True]:
 dest=out/('armature_and_passive_free' if passive else 'armature_only');dest.mkdir();scene,*_=scene_and_cal(root,dest,True,True,True,passive);m=mujoco.MjModel.from_xml_path(str(scene));j=m.actuator_trnid[:29,0];av=m.jnt_dofadr[j]
 expected=np.array([audit['body_armatures'][m.joint(int(k)).name] for k in j]);assert np.array_equal(m.dof_armature[av],expected)
 h=m.jnt_dofadr[m.actuator_trnid[29:43,0]];bh=base.jnt_dofadr[base.actuator_trnid[29:43,0]]
 assert np.array_equal(m.dof_armature[h],base.dof_armature[bh]) and np.array_equal(m.dof_frictionloss[h],base.dof_frictionloss[bh])
 assert np.array_equal(m.actuator_ctrlrange,base.actuator_ctrlrange)
 assert m.neq==1 and m.eq_obj1id[0]==m.body('pelvis').id and m.eq_obj2id[0]==0
 assert m.jnt_type[m.body('red_cube').jntadr]==mujoco.mjtJoint.mjJNT_FREE
 if passive:assert not m.dof_damping[av].any() and not m.dof_frictionloss[av].any()
 else:assert np.array_equal(m.dof_damping[av],base.dof_damping[base.jnt_dofadr[base.actuator_trnid[:29,0]]])
 records.append(dict(passive_free=passive,scene_sha=s.sha(scene),body_armatures=m.dof_armature[av].tolist()))
r=dict(physical_steps=0,pass_count=12,source_sha=s.sha(root/'sonic_grasp.py'),tests=['29 named inertias match official parsed mapping','finger inertias/friction unchanged','all original actuator limits unchanged','only pelvis-world fixture','object free joint preserved','passive-free distinguished from inertias-only'],records=records)
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
