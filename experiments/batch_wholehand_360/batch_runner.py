"""Finite audited scheduler, at most eight two-core workers, no GPU."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','LP_NUM_THREADS']:os.environ[key]='1'
import resource
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import sys,json,hashlib,time,datetime,subprocess,threading,shutil,argparse,traceback
from concurrent.futures import ThreadPoolExecutor,as_completed
R=Path(__file__).resolve().parent;B=Path('/home/group4/group4_dasc7606c');T=R.name
PY='/data/group4/20261004-205550-qoder-1280b420/env/bin/python'
RULES='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
lock=threading.Lock();start=time.monotonic()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def record(text):
    with lock:
        with (B/'logs'/T/'steps.md').open('a') as f:f.write('\n- '+now()+' '+text+'\n')
def write_state(row):
    with lock:
        temp=R/'state'/(row['id']+'.json.tmp');temp.write_text(json.dumps(row,indent=2));temp.replace(R/'state'/(row['id']+'.json'))
def run_stage(row,stage,command,slot,timeout):
    env=os.environ.copy();env.update({'TMPDIR':str(R/'tmp'),'XDG_CACHE_HOME':str(R/'tmp/cache'),
             'MUJOCO_GL':'osmesa','PYOPENGL_PLATFORM':'osmesa',
             'LD_LIBRARY_PATH':'/data/group4/20261008-220500-codex-6c40bf04/lib','PYTHONDONTWRITEBYTECODE':'1'})
    log=R/'logs'/(row['id']+'-'+stage+'.log');pair=f'{80+2*slot},{81+2*slot}'
    args=['timeout','--kill-after=5',str(timeout),'taskset','-c',pair]+command
    info={'stage':stage,'command':args,'cwd':str(R),'cpu_affinity':pair,'timeout_s':timeout,'started':now(),'log':str(log)}
    begun=time.monotonic()
    with log.open('xb') as output:
        proc=subprocess.Popen(args,cwd=R,env=env,stdout=output,stderr=subprocess.STDOUT)
        info['pid']=proc.pid;info['proc_start_ticks']=Path(f'/proc/{proc.pid}/stat').read_text().split()[21]
        row['stages'].append(info);row['status']=stage;write_state(row)
        record(f"{row['id']} {stage} START pid={proc.pid} cores={pair} cwd={R} timeout={timeout}s command={json.dumps(args)} log={log}")
        # GNU timeout owns only this launched command's process group, including encoder children.
        info['rc']=proc.wait();info['ended']=now();info['wall_s']=time.monotonic()-begun
    info['log_sha']=sha(log);write_state(row)
    record(f"{row['id']} {stage} END rc={info['rc']} wall={info['wall_s']:.3f}s log_sha={info['log_sha']}")
    return info['rc']
def run_trial(config,slot):
    row={'id':config['id'],'group':config['group'],'trial_config':config,'status':'starting','stages':[],
         'started':now(),'manifest_sha':sha(R/'manifest.json'),'source_sha':manifest['sources_sha']}
    existing=R/'state'/(config['id']+'.json')
    if existing.exists():
        old=json.loads(existing.read_text())
        if old.get('status')=='completed' and old['manifest_sha']==row['manifest_sha']:
            episode=R/'out'/config['id'];meta=json.loads((episode/'replay/replay.json').read_text())
            assert meta['video_sha']==sha(episode/'replay/grasp.mp4') and meta['source_result_sha']==sha(episode/'result.json')
            assert meta['source_trajectory_sha']==sha(episode/'trajectory.npz');return old
        raise RuntimeError(f"Existing incomplete state {config['id']}; no overwrite or silent retry")
    write_state(row)
    try:
        assert sha(B/'AGENTS.md')==RULES,'RULES_CHANGED_STOP_NEW_WORK'
        assert time.monotonic()-start<28800,'BATCH_WALL_BOUND'
        assert shutil.disk_usage(R).free>30*1024**3,'DATA_FREE_SPACE_BOUND'
        for f,expected in manifest['sources_sha'].items():assert sha(R/f)==expected,'SOURCE_CHANGED '+f
        rc=run_stage(row,'plan',[PY,'-B',str(R/'batch_plan.py'),'--config',str(R/'configs'/(config['id']+'.json'))],slot,600)
        if rc:
            row['infrastructure_subtype']='planning_timeout' if rc in [124,137] else 'planning_error'
            raise RuntimeError(f'planning command exit {rc}')
        args=[PY,'-B',str(R/'execute_batch.py'),'--plan','plan_'+config['id'],'--name',config['id'],
              '--native-mesh','--retract-raise','--time-scale','2','--gravity-arm-scale',str(config['gravity_arm_scale'])]
        if config['wrist_servo']:args+=['--wrist-servo']
        if config['no_grip']:args+=['--no-grip']
        rc=run_stage(row,'physics',args,slot,600)
        if rc:
            row['infrastructure_subtype']='physics_timeout' if rc in [124,137] else 'physics_error'
            raise RuntimeError(f'physics command exit {rc}')
        result=json.loads((R/'out'/config['id']/'result.json').read_text())
        row.update({'classification':result['classification'],'success':result['success'],'grasp_path_executed':result['grasp_path_executed'],
                    'result_sha':sha(R/'out'/config['id']/'result.json'),'runtime_stamp':result['runtime_stamp']})
        rc=run_stage(row,'render',[PY,'-B',str(R/'render_batch.py'),config['id']],slot,600)
        if rc:
            row['status']='video_error';row['video_valid']=False;row['error']=f'render command exit {rc}'
            row['infrastructure_subtype']='render_timeout' if rc in [124,137] else 'render_error'
        else:
            meta=json.loads((R/'out'/config['id']/'replay/replay.json').read_text())
            assert meta['id']==config['id'] and meta['source_result_sha']==row['result_sha']
            assert meta['video_sha']==sha(R/'out'/config['id']/'replay/grasp.mp4') and meta['decode_verified']
            row['status']='completed';row['video_valid']=True;row['video_sha']=meta['video_sha']
    except Exception as error:
        row['error']=str(error);row['traceback']=traceback.format_exc();row['status']='infrastructure_error'
        row.setdefault('classification','infrastructure_error');row.setdefault('success',False)
        record(config['id']+' ERROR '+row['traceback'])
    row['ended']=now();write_state(row)
    return row
def worker(slot,configs):
    rows=[]
    for config in configs:
        if sha(B/'AGENTS.md')!=RULES or time.monotonic()-start>=28800:
            record(f'Worker{slot} STOP new work, rules/wall bound');break
        row=run_trial(config,slot);rows.append(row)
        with lock:
            with (R/'results-ledger.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps({'id':row['id'],'classification':row.get('classification'),'status':row['status'],'ended':row['ended']}),flush=True)
    return rows
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);p.add_argument('--ids',nargs='*');args=p.parse_args()
    assert 1<=args.workers<=8
    manifest=json.loads((R/'manifest.json').read_text())
    assert sha(R/'manifest.json')==(R/'manifest.sha256').read_text().split()[0]
    assert sha(B/'AGENTS.md')==RULES
    assert sha(R/'model-assets.json')==manifest['model_asset_manifest_sha']
    for path,expected in json.loads((R/'model-assets.json').read_text()).items():assert sha(path)==expected,'SOURCE_ASSET_CHANGED '+path
    configs=manifest['trials']
    if args.ids:
        configs=[t for t in configs if t['id'] in args.ids];assert len(configs)==len(set(args.ids))
    # Interleave conditions so early progress covers each group, without selecting by outcome.
    groups=['A','B','C','D','NGR','NWS','NGF'];ordered=[]
    for i in range(100):
        for group in groups:
            matching=[t for t in configs if t['group']==group and int(t['id'][len(group):])==i];ordered+=matching
    record(f'Batch START finite rows={len(ordered)} workers={args.workers} parent_pid={os.getpid()} manifest_sha={sha(R/"manifest.json")}')
    lifecycle={'pid':os.getpid(),'started':now(),'cwd':str(R),'command':sys.argv,'workers':args.workers,'rows':len(ordered),
               'proc_start_ticks':Path(f'/proc/{os.getpid()}/stat').read_text().split()[21],'rules_sha':RULES,'manifest_sha':sha(R/'manifest.json')}
    (R/'state/lifecycle.json').write_text(json.dumps(lifecycle,indent=2))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(worker,i,ordered[i::args.workers]) for i in range(args.workers)]
        rows=[]
        for future in as_completed(futures):rows+=future.result()
    lifecycle.update({'ended':now(),'finished_rows':len(rows),'wall_s':time.monotonic()-start})
    (R/'state/lifecycle.json').write_text(json.dumps(lifecycle,indent=2));record('Batch END '+json.dumps(lifecycle))
