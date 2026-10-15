"""Read-only comparison, original physics unchanged."""
import os,resource
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import numpy as np,json,sys
R=Path(__file__).resolve().parent;name=sys.argv[1];other=sys.argv[2]
rows={};bp=R/'out'/name;ap=R/'out'/other
with np.load(bp/'trajectory.npz',allow_pickle=False) as b,np.load(ap/'trajectory.npz',allow_pickle=False) as a:
    for key in ['qpos','qvel','ctrl','body_reference','hand_reference','cube_pos']:
        n=min(len(a[key]),len(b[key]));different=np.flatnonzero(np.any(a[key][:n]!=b[key][:n],axis=1))
        before=b['time'][:n]<34
        rows[key]={'first_different_s':float(b['time'][different[0]]) if len(different) else None,
                   'max_difference_before34':float(np.max(abs(a[key][:n][before]-b[key][:n][before]))),
                   'initial_B':b[key][0].tolist(),'initial_ablation':a[key][0].tolist()}
    stamps=[json.loads(str(x['runtime_stamp_json'])) for x in [b,a]]
    for out in [bp,ap]:
        plan=json.loads((out/'execution_plan.json').read_text());rows[out.name+'_plan']=plan
result={'baseline':name,'ablation':other,'diagnostics':rows,'runtime_stamp':stamps[0],
        'scope':'read-only sampled comparison, not new simulation; no counterfactual assertion'}
with (R/(name+'-'+other+'-diagnostic.json')).open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({k:{x:v[x] for x in ['first_different_s','max_difference_before34']} for k,v in rows.items() if 'first_different_s' in v},indent=2))
