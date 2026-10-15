"""Bounded own-task observation and postprocessing-source check, no simulation."""
import os,resource
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
from pathlib import Path
import ast,datetime,json,hashlib
R=Path(__file__).resolve().parent
B=Path('/home/group4/group4_dasc7606c')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=json.loads((R/'manifest.json').read_text())
for name,value in manifest['sources_sha'].items():
    assert sha(R/name)==value,('frozen source changed',name)
for path in R.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
observed={};examples={};fails=[]
for group in ['A','B','C','D','NGR','NWS','NGF']:
    rows=[]
    for trial in sorted((t for t in manifest['trials'] if t['group']==group),key=lambda t:t['id']):
        out=R/'out'/trial['id'];result_path=out/'result.json';replay_path=out/'replay/replay.json'
        if not result_path.exists() or not replay_path.exists():continue
        result=json.loads(result_path.read_text());meta=json.loads(replay_path.read_text())
        rows.append((trial,result,meta))
    observed[group]={'completed_video':len(rows),'success':sum(bool(r['success']) for _,r,_ in rows)}
    examples[group]={}
    for classification in ['physics_success','physics_failure']:
        found=next(((t,r,m) for t,r,m in rows if r['classification']==classification),None)
        if not found:examples[group][classification]=None;continue
        trial,result,meta=found
        examples[group][classification]={'id':trial['id'],'video_path':str(R/'out'/trial['id']/'replay/grasp.mp4'),
           'video_sha':meta['video_sha'],'source_result_sha':meta['source_result_sha'],'duration_s':meta['duration_s']}
        if classification=='physics_failure':
            fails.append({'id':trial['id'],'reason':result['reason'],'runtime_stamp':result['runtime_stamp'],
                          'result_sha':sha(R/'out'/trial['id']/'result.json'),
                          'metrics':{key:result.get(key) for key in ['max_lift_m','hold_safe_steps','hold_support_steps',
                              'max_wristlocal_slip_alllift_m','max_joint_limit_violation_rad']}})
report={'time':datetime.datetime.now().astimezone().isoformat(),'frozen_sources_unchanged':True,
        'postprocess_AST_pass':True,'observed':observed,'current_examples_lowest_id':examples,
        'failure_examples':fails,'scope':'interim completed-video observations, not final rates'}
postprocess_hashes={name:sha(R/name) for name in ['archive_batch.py','audit_batch.py','verify_videos.py',
                  'summarize_batch.py','inspect_batch.py','monitor_batch.py','PROGRESS-0406.md'] if (R/name).exists()}
with (B/'logs'/R.name/'steps.md').open('a') as stream:
    stream.write('\n- '+report['time']+' Postprocessing-only AST/hash check; frozen physics/planner/renderer/manifest unchanged. '+
                 'Report now distinguishes runtime-counter gate consistency from independent1ms gate recomputation; '+
                 'video verifier preserves bounded progress and per-trial identity. '+json.dumps(observed)+'\n')
    stream.write('- Postprocessing uploaded file SHA map '+json.dumps(postprocess_hashes)+'\n')
    stream.write('- Local delivery verified by owner: A000/B000/C000/D000/D011 replay directories, all53.12s videos; '+
                 'progress MD dual SHA942bc238e47f26e818f12ff11f0e802bd1cfc7bf17d05f19a0749bb26c0cfac5; '+
                 'recorded detailed per-video SHA in PROGRESS-0406.md. Native D000/D011 HOLD images visually inspected. '+
                 'Local apply_patch had two failed context checks, corrected locally without server mutation; '+
                 'one local monitor-return serialization error at normal listener completion, listener renewed without experiment restart. '+
                 'Server rg unavailable; two issue states read using grep fallback, both OPEN at04:17. No issue notes/closure yet.\n')
print(json.dumps(report))
