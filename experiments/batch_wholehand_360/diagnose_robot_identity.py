"""Compare retained baseline/fresh XML identities and compiled arrays, no integration."""
import os,resource
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import json,hashlib,difflib,datetime
import numpy as np,mujoco
R=Path(__file__).resolve().parent;B=Path('/home/group4/group4_dasc7606c')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
models=[];rows=[]
for name in ['A000','B000']:
    out=R/'out'/name;m=mujoco.MjModel.from_xml_path(str(out/'scene.xml'))
    cube=m.body('red_cube').id;cubegeom=int(np.flatnonzero(m.geom_bodyid==cube)[0])
    m.opt.timestep=.001;m.opt.impratio=10
    right=[g for g in range(m.ngeom) if m.body(int(m.geom_bodyid[g])).name.startswith(('right_hand_','right_wrist_','right_elbow','right_shoulder')) and m.geom_contype[g]]
    for g in [cubegeom]+right:m.geom_margin[g]=.001;m.geom_solref[g,:2]=[.02,1]
    m.dof_armature[m.jnt_dofadr[m.actuator_trnid[36:43,0]]]=.1
    models.append(m)
    result=json.loads((out/'result.json').read_text());contract=json.loads((out/'episode_contract.json').read_text())
    rows.append({'id':name,'runtime_stamp':result['runtime_stamp'],'contract':contract,
                 'robot_xml_sha':sha(out/'robot.xml'),'initial_robot_pos':m.body_pos[:cube].tolist()})
differences={};equal=[]
for key in dir(models[0]):
    if key.startswith('_'):continue
    try:a=getattr(models[0],key);b=getattr(models[1],key)
    except Exception:continue
    if not isinstance(a,np.ndarray) or not isinstance(b,np.ndarray):continue
    if np.array_equal(a,b):equal.append(key);continue
    row={'shape_a':a.shape,'shape_b':b.shape,'dtype':str(a.dtype)}
    if a.shape==b.shape and a.dtype.kind in 'fiu' and a.size:
        delta=abs(a.astype(float)-b.astype(float));row.update(max_abs_difference=float(delta.max()),changed_indices=np.argwhere(delta!=0)[:20].tolist())
    differences[key]=row
diff=list(difflib.unified_diff((R/'out/A000/robot.xml').read_text().splitlines(),(R/'out/B000/robot.xml').read_text().splitlines(),fromfile='A000 retained baseline',tofile='B000 fresh build',n=1))
report={'scope':'read-only XML and compiled-model diagnostics; no mj_step; object positions differ by predeclared XY; in-memory controller contact recipe reproduced',
        'equal_compiled_arrays':equal,'differing_compiled_arrays':differences,'xml_diff':diff,'rows':rows}
with (R/'robot-identity-diagnostic.json').open('x') as f:json.dump(report,f,indent=2)
with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- '+datetime.datetime.now().astimezone().isoformat()+' Readonly robot identity diagnostic '+str(R/'robot-identity-diagnostic.json')+' sha='+sha(R/'robot-identity-diagnostic.json')+'\n')
print(json.dumps({'differences':differences,'xml_diff':diff,'rows':[{k:v for k,v in row.items() if k in ['id','robot_xml_sha']} for row in rows]}))
