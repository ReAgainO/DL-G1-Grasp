"""A bounded sequence, with an explicit run ledger and preserved failures."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path('/data/group4/20261006-093203-codex-6385a841')
PY327='/data/group4/20261004-205550-qoder-1280b420/env/bin/python'
PY314='/home/group4/group4_dasc7606c/envs/render/bin/python'
cases={
 'pair327':[(PY327,'matched_prior0','matched0_327',[])],
 'pairs314':[(PY314,'matched_prior08','matched08_314',[]),(PY314,'matched_prior0','matched0_314',[])],
 'negative327':[(PY327,'matched_prior08','ng327',['--no-grip']),(PY327,'matched_prior08','po327',['--pad-off'])],
 'negative314':[(PY314,'matched_prior08','ng314',['--no-grip']),(PY314,'matched_prior08','po314',['--pad-off'])],
}
group=sys.argv[1]
assert group in cases
assert len(cases[group])<=3
results=[]
for interpreter,plan,name,flags in cases[group]:
 if (ROOT/'out'/name).exists(): raise RuntimeError('Refuse to overwrite: '+name)
 import os
 env=os.environ.copy();env['STAGE_PY']=interpreter
 start=time.monotonic()
 cmd=['bash',str(ROOT/'run.sh'),'grasp.py',str(ROOT),str(ROOT/'out'/plan/'plan.npz'),name,*flags]
 log=ROOT/'out'/('batch-'+name+'.log')
 with log.open('x') as f:
  r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=140)
 payload=dict(name=name,exit=r.returncode,wall_s=time.monotonic()-start,log=str(log))
 if (ROOT/'out'/name/'result.json').exists():
  d=json.loads((ROOT/'out'/name/'result.json').read_text())
  payload.update(version=d['runtime_stamp']['mujoco_version'],success=d['success'],
                 hold_min_lift_m=d['hold_min_lift_m'],max_lift_m=d['max_lift_m'],tracking_rms=d['tracking_rms_rad'])
 results.append(payload);print(json.dumps(payload),flush=True)
 if r.returncode: raise RuntimeError('Run failed, inspect preserved log '+str(log))
(ROOT/'out'/('batch-'+group+'.json')).write_text(json.dumps(results,indent=2)+'\n')
