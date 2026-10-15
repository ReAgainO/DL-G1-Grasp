"""Read official config AST as data; do not import/run IsaacLab training code."""
import ast,json,re,shutil
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s
root=Path(__file__).resolve().parent;out=root/'out/official-dynamics.json';assert not out.exists()
source=Path('/home/group4/group4_dasc7606c/repos/sonic/GR00T-WholeBodyControl/gear_sonic/envs/manager_env/robots/g1.py')
dest=root/'official_refs/g1_training.py';assert not dest.exists();shutil.copy2(source,dest);assert s.sha(source)==s.sha(dest)
tree=ast.parse(dest.read_text());env={}
def val(n):
 if isinstance(n,ast.Constant):return n.value
 if isinstance(n,ast.Name):return env[n.id]
 if isinstance(n,(ast.List,ast.Tuple)):return [val(x) for x in n.elts]
 if isinstance(n,ast.Dict):return {val(k):val(v) for k,v in zip(n.keys,n.values)}
 if isinstance(n,ast.BinOp):
  a,b=val(n.left),val(n.right)
  if isinstance(n.op,ast.Mult):return a*b
  if isinstance(n.op,ast.Pow):return a**b
  if isinstance(n.op,ast.Add):return a+b
 if isinstance(n,ast.UnaryOp) and isinstance(n.op,ast.USub):return -val(n.operand)
 raise ValueError('Not literal data: '+ast.dump(n))
cfg=None
for n in tree.body:
 if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
  key=n.targets[0].id
  if key=='G1_CYLINDER_MODEL_12_DEX_CFG':cfg=n.value
  if key.startswith(('ARMATURE_','NATURAL_FREQ','DAMPING_RATIO','STIFFNESS_','DAMPING_')):env[key]=val(n.value)
assert isinstance(cfg,ast.Call)
act=next(k.value for k in cfg.keywords if k.arg=='actuators');groups=[]
for label,call in zip(act.keys,act.values):
 kw={k.arg:k.value for k in call.keywords};groups.append(dict(name=val(label),patterns=val(kw['joint_names_expr']),armature=val(kw['armature'])))
m=mujoco.MjModel.from_xml_path(str(root/'src/g1/scene_grasp_hand.xml'));ids=m.actuator_trnid[:29,0];records=[];mapping={}
for i,j in enumerate(ids):
 name=m.joint(int(j)).name;matches=[(g,p) for g in groups for p in g['patterns'] if re.fullmatch(p,name)];assert len(matches)==1,name
 g,p=matches[0];expected=g['armature'][p] if isinstance(g['armature'],dict) else g['armature'];mapping[name]=expected
 assert abs(expected-s.KP[i]/(10*2*np.pi)**2)<1e-10
 actual=float(m.dof_armature[m.jnt_dofadr[j]])
 records.append(dict(joint=name,xml_armature=actual,official_training_armature=expected,ratio=actual/expected,xml_passive_damping=float(m.dof_damping[m.jnt_dofadr[j]]),xml_frictionloss=float(m.dof_frictionloss[m.jnt_dofadr[j]])))
r=dict(physical_steps=0,official_source=str(source),official_source_sha=s.sha(dest),official_source_url='https://github.com/NVlabs/GR00T-WholeBodyControl/blob/main/gear_sonic/envs/manager_env/robots/g1.py',parse_method='AST constants and arithmetic only, no executing official source',port_KP_matches_official_armatures=True,body_armatures=mapping,records=records,source_sha=s.sha(__file__),mujoco_version=mujoco.__version__)
out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(physical_steps=0,official_source_sha=r['official_source_sha'],right_arm_records=records[22:29],mapping_matches_port=True),indent=2))
