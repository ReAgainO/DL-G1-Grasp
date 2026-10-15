"""Own-task setup and bounded pilots. All changes logged; existing files not overwritten."""
import os,json,hashlib,subprocess,shutil,datetime,sys,resource
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
R=Path(__file__).resolve().parent;B=Path('/home/group4/group4_dasc7606c');T=R.name
RULES='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
PY='/data/group4/20261004-205550-qoder-1280b420/env/bin/python'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def record(s):
    with (B/'logs'/T/'steps.md').open('a') as f:f.write('\n- '+datetime.datetime.now().isoformat()+' '+s+'\n')
assert sha(B/'AGENTS.md')==RULES
action=sys.argv[1];suffix='2' if action.endswith('2') else '';action=action.rstrip('2')
env=os.environ.copy();env.update({key:'1' for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','LP_NUM_THREADS']})
env.update({'TMPDIR':str(R/'tmp'),'XDG_CACHE_HOME':str(R/'tmp/cache'),'MUJOCO_GL':'osmesa','PYOPENGL_PLATFORM':'osmesa',
            'LD_LIBRARY_PATH':'/data/group4/20261008-220500-codex-6c40bf04/lib','PYTHONDONTWRITEBYTECODE':'1'})
if action=='pilots':
    record('Uploaded own batch source from local apply_patch; copied prior own task library and baseline plan read-only. New source preparation; pilots excluded from360.')
    configs=[{'id':'PBASE','xy_m':[.35,-.18],'edge_m':.08,'root_x_m':0},
             {'id':'PRAND','xy_m':[.369,-.197],'edge_m':.08,'root_x_m':0},
             {'id':'PSIZE','xy_m':[.337,-.163],'edge_m':.088,'root_x_m':0},
             {'id':'PBACK','xy_m':[.337,-.163],'edge_m':.088,'root_x_m':-.02}]
    for row in configs:
        row['id']+=suffix
        row.update({'group':'PILOT','mass_kg':.12,'sampling_seed':None,'no_grip':False,'wrist_servo':True,'gravity_arm_scale':1})
        path=R/'pilots'/(row['id']+'.json')
        with path.open('x') as f:json.dump(row,f,indent=2)
    (R/'tmp/cache').mkdir(exist_ok=True)
    record('Pilot configurations frozen: '+json.dumps(configs));print(json.dumps(configs))
elif action=='runpilots':
    from concurrent.futures import ThreadPoolExecutor
    import threading,time
    pilotlock=threading.Lock()
    def run_pilot(pair):
        slot,name=pair;configs=R/'pilots'/(name+'.json')
        commands=[('plan',180,[PY,'-B',str(R/'batch_plan.py'),'--config',str(configs)]),
                  ('physics',600,[PY,'-B',str(R/'execute_batch.py'),'--plan','plan_'+name,'--name',name,'--native-mesh','--retract-raise','--wrist-servo']),
                  ('render',600,[PY,'-B',str(R/'render_batch.py'),name])]
        rows=[]
        for stage,bound,command in commands:
            args=['timeout','--kill-after=5',str(bound),'taskset','-c',f'{80+slot*2},{81+slot*2}']+command
            log=R/'logs'/(name+'-'+stage+'.log');begun=time.time()
            with log.open('xb') as f:p=subprocess.Popen(args,env=env,cwd=R,stdout=f,stderr=subprocess.STDOUT)
            with pilotlock:record(f'Pilot {name} {stage} START pid={p.pid} command={args} log={log}')
            rc=p.wait();row={'stage':stage,'rc':rc,'wall_s':time.time()-begun,'command':args,'pid':p.pid,'log':str(log),'log_sha':sha(log)};rows.append(row)
            with pilotlock:record(f'Pilot {name} {stage} END '+json.dumps(row))
            if rc:break
        (R/'pilots'/(name+'-receipt.json')).write_text(json.dumps(rows,indent=2));print(json.dumps({'id':name,'stages':rows}),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run_pilot,enumerate([x+suffix for x in ['PBASE','PRAND','PSIZE','PBACK']])))
    (R/'pilots'/('done'+suffix+'.json')).write_text(json.dumps({'ended':datetime.datetime.now().isoformat()}))
elif action=='pilotlaunch':
    args=['taskset','-c','80-87','/usr/bin/python3','-B',str(R/'server_prepare.py'),'runpilots'+suffix]
    log=(R/'logs'/('pilots'+suffix+'.log')).open('xb')
    p=subprocess.Popen(args,cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    receipt={'pid':p.pid,'command':args,'cwd':str(R),'started':datetime.datetime.now().isoformat(),
             'proc_start_ticks':Path(f'/proc/{p.pid}/stat').read_text().split()[21]}
    (R/'pilots'/('launch'+suffix+'.json')).write_text(json.dumps(receipt,indent=2));record('Pilot launch '+json.dumps(receipt));print(json.dumps(receipt))
elif action=='freeze':
    assert (R/'pilots/done2.json').exists(),'Wait for all preflight stages'
    assert (R/'pilots/verification.json').exists()
    bench=json.loads((R/'out/PBASE2/replay_lp2/replay.json').read_text());assert bench['decode_verified'] and bench['mesa_lp_threads']==2
    record('Pre-freeze bounded LP2 renderer benchmark decoded; source SHA '+bench['renderer_sha']+'; all pilot14-array baseline comparisons exact.')
    for name in ['PBASE2','PRAND2','PSIZE2','PBACK2']:
        receipt=json.loads((R/'pilots'/(name+'-receipt.json')).read_text())
        assert len(receipt)==3 and all(row['rc']==0 for row in receipt),(name,receipt)
        replay=json.loads((R/'out'/name/'replay/replay.json').read_text());assert replay['decode_verified'] and replay['duration_s']>=52
    import ast
    for path in R.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    record('Preflight complete; freezing source and300+60 manifest before counted trials.')
    command=['timeout','180','taskset','-c','80,81',PY,'-B',str(R/'make_trials.py')]
    p=subprocess.run(command,cwd=R,env=env,capture_output=True,text=True);record(f'{command} rc={p.returncode}\n{p.stdout}\n{p.stderr}');print(p.stdout,p.stderr)
    assert p.returncode==0
    for f in ['execute_batch.py','batch_plan.py','render_batch.py','batch_runner.py','make_trials.py','wholehand_side.py']:
        shutil.copy2(R/f,R/'source-snapshots'/f)
    record('Frozen manifest '+sha(R/'manifest.json'))
elif action=='renderbench':
    command=['timeout','--kill-after=5','600','taskset','-c','80,81',PY,'-B',str(R/'render_batch.py'),'PBASE2','replay_lp2']
    log=(R/'logs/renderbench.log').open('xb')
    p=subprocess.Popen(command,cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    record('Pre-freeze graphics bench LP2 bounded two-core START '+json.dumps({'pid':p.pid,'command':command,'cwd':str(R)}));print(p.pid)
elif action=='verifypilots':
    command=['timeout','60','taskset','-c','80,81',PY,'-B',str(R/'verify_pilots.py')]
    p=subprocess.run(command,cwd=R,env=env,capture_output=True,text=True);record(f'Pilot verification {command} rc={p.returncode}\n{p.stdout}\n{p.stderr}');print(p.stdout,p.stderr)
    assert p.returncode==0
elif action=='launch':
    record('Resource pre-launch reads')
    for cmd in [['df','-h','/home','/data'],['free','-h']]:
        p=subprocess.run(cmd,capture_output=True,text=True);record(f'{cmd} rc={p.returncode}\n{p.stdout}');print(p.stdout)
    for n in ['cpu','memory','io']:record('/proc/pressure/'+n+' '+Path('/proc/pressure',n).read_text())
    command=['taskset','-c','80-95','/usr/bin/python3','-B',str(R/'batch_runner.py'),'--workers','8']
    output=(R/'logs/batch.log').open('xb')
    process=subprocess.Popen(command,cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    receipt={'pid':process.pid,'command':command,'cwd':str(R),'started':datetime.datetime.now().isoformat(),
             'proc_start_ticks':Path(f'/proc/{process.pid}/stat').read_text().split()[21],'log':str(R/'logs/batch.log')}
    (R/'state/launch.json').write_text(json.dumps(receipt,indent=2));record('Detached finite batch launch '+json.dumps(receipt));print(json.dumps(receipt))
else:raise ValueError(action)
