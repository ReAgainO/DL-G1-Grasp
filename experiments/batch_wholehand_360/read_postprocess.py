"""Bounded small progress/provenance reader; not a physical evidence generator."""
from pathlib import Path
import json,hashlib,collections,datetime,resource
resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,256*1024**2))
R=Path(__file__).resolve().parent;B=Path('/home/group4/group4_dasc7606c')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
row={'time':datetime.datetime.now().astimezone().isoformat(),'scope':'readonly progress and audit metadata; no new simulation/measurement'}
audit=R/'audit-final.json'
if audit.exists():
    data=json.loads(audit.read_text())
    warning_ids={w.get('ablation') for w in data['warnings']}
    row['audit']={'path':str(audit),'sha':sha(audit),'checked':data['checked'],'failures':len(data['failures']),
                  'A_equal':sum(data['fixed_A_arrays_bitwise_equal'].values()),'warnings':len(data['warnings']),
                  'warning_groups':dict(collections.Counter(name[:-3] for name in warning_ids if name)),
                  'reference_identity_pairs':sum(p.get('strict_exogenous_reference_identity',False) for p in data['ablation_pairs'])}
progress=sorted(R.glob('video-verification-progress-*.json'))
if progress:
    data=json.loads(progress[-1].read_text())
    row['video_progress']={'checked':data['checked_videos'],'failures':len(data['failures']),'attempt':data['attempt_id'],'wall_s':data['wall_s']}
if (R/'summary.json').exists():
    data=json.loads((R/'summary.json').read_text())
    row['summary']={'groups':data['groups'],'pairs':{name:{key:value for key,value in pair.items() if key!='pairs'} for name,pair in data['paired_comparisons'].items()},
                    'failure_gates':{g:dict(collections.Counter(gate.split('\uFF1A',1)[0] for t in data['trials'] if t['group']==g and t['outcome']=='physics_failure' for gate in t['failed_runtime_gates'])) for g in data['groups']}}
with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- '+row['time']+' Readonly postprocess progress '+json.dumps({k:v for k,v in row.items() if k!='summary'})+'\n')
print(json.dumps(row))
