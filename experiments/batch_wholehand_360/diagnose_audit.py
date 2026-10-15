"""Read-only traceback for the retained failed audit; no physical changes."""
import os, resource
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import json, hashlib, ast, traceback, datetime
import numpy as np, mujoco, xml.etree.ElementTree as ET
R=Path(__file__).resolve().parent
B=Path('/home/group4/group4_dasc7606c')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
manifest=json.loads((R/'manifest.json').read_text())
tree=ast.parse((R/'audit_batch.py').read_text())
nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='inspect' or isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected_common' for t in node.targets)]
namespace={'R':R,'sha':sha,'manifest':manifest,'json':json,'np':np,'mujoco':mujoco,'ET':ET}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(R/'audit_batch.py'),'exec'),namespace)
rows=[]
for name in ['A000','B000']:
    config=next(c for c in manifest['trials'] if c['id']==name)
    plan=json.loads((R/'out'/('plan_'+name)/'plan.json').read_text())
    try:
        row=namespace['inspect'](config)
    except Exception as error:
        row={'id':name,'error':repr(error),'traceback':traceback.format_exc()}
    row.update(config=config,plan_trial_config=plan.get('trial_config'),plan_stamp=plan.get('runtime_stamp'),plan_keys=list(plan))
    rows.append(row)
report={'scope':'readonly first-audit diagnosis; original audit_batch.json/log preserved; no simulation/parameter/gate change',
        'audit_source_sha':sha(R/'audit_batch.py'),'rows':rows}
with (R/'audit-first-diagnostic.json').open('x') as f:json.dump(report,f,indent=2)
with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- '+datetime.datetime.now().astimezone().isoformat()+' Retained initial audit failure: all A rows triggered assertion; readonly diagnosis '+str(R/'audit-first-diagnostic.json')+' sha='+sha(R/'audit-first-diagnostic.json')+'\n')
print(json.dumps(report))
