"""Finite experiments, recorded resource bounds, immutable per-wave inputs."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key] = '1'
import resource
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

R=Path(__file__).resolve().parent
B=Path('/home/group4/group4_dasc7606c')
OLD=Path('/data/group4/20261009-021611-codex-415484ce')
PY='/data/group4/20261004-205550-qoder-1280b420/env/bin/python'
RULES='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.datetime.now().astimezone().isoformat()
lock=threading.Lock()
assert R.name=='20261009-170228-codex-fcd727b9'

def record(value):
    with lock:
        with (B/'logs'/R.name/'steps.md').open('a') as f:
            f.write('\n- '+now()+' '+value+'\n')

def new_json(path,value):
    with path.open('x') as f:
        json.dump(value,f,indent=2)

env=os.environ.copy()
env.update({'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(R/'tmp'), 'XDG_CACHE_HOME':str(R/'tmp/cache'),
            'MUJOCO_GL':'osmesa','PYOPENGL_PLATFORM':'osmesa','LP_NUM_THREADS':'2',
            'LD_LIBRARY_PATH':'/data/group4/20261008-220500-codex-6c40bf04/lib'})

def check_rules():
    assert sha(B/'AGENTS.md')==RULES,'Rules drift: do not start next job'

def resource_probe():
    for cmd in [['df','-h','/home','/data','/tmp'],['free','-g']]:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
        record(f'Resource probe command={cmd} rc={p.returncode}\n{p.stdout}{p.stderr}')
    for kind in ['cpu','memory','io']:
        record('PSI '+kind+' '+Path('/proc/pressure',kind).read_text())

def run_one(pair):
    slot,row=pair
    check_rules()
    assert all(sha(R/name)==digest for name,digest in row['source_hashes'].items())
    cmd=[PY,'-B',str(R/'execute_jitter.py'),'--plan','plan_'+row['source_episode'],
         '--source-episode',row['source_episode'],'--name',row['id'],
         '--native-mesh','--retract-raise','--wrist-servo','--arm-target-tau',str(row['tau']),
         '--arm-damping',str(row['damping']),'--servo-gain',str(row['servo_gain']),
         '--change-start',str(row['start'])]
    if row.get('no_grip'):
        cmd.append('--no-grip')
    command=['timeout','--kill-after=5','580','taskset','-c',f'{80+slot*2},{81+slot*2}']+cmd
    log=R/'logs'/(row['id']+'-physics.log')
    begun=time.time()
    with log.open('xb') as f:
        p=subprocess.Popen(command,cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
    record('Physics START '+json.dumps({'id':row['id'],'pid':p.pid,'command':command,'cwd':str(R),'log':str(log)}))
    rc=p.wait()
    receipt={'id':row['id'],'pid':p.pid,'rc':rc,'wall_s':time.time()-begun,'command':command,'log':str(log),'log_sha':sha(log),'ended':now()}
    result=R/'out'/row['id']/'result.json'
    if result.exists():
        data=json.loads(result.read_text())
        receipt.update({'success':data['success'],'reason':data['reason'],'result_sha':sha(result)})
    new_json(R/'configs'/(row['id']+'-receipt.json'),receipt)
    record('Physics END '+json.dumps(receipt))
    print(json.dumps(receipt),flush=True)
    return receipt

action=sys.argv[1]
wave=sys.argv[2] if len(sys.argv)>2 else 'wave1'
assert wave.replace('_','').isalnum()
if action=='freeze':
    check_rules()
    assert wave=='wave1'
    import ast
    for name in ['execute_jitter.py','jitter_control.py','test_jitter_control.py','run_wave.py']:
        ast.parse((R/name).read_text(),filename=name)
    subprocess.run([PY,'-B',str(R/'test_jitter_control.py')],cwd=R,env=env,check=True,timeout=30)
    (R/'tmp/cache').mkdir(exist_ok=True)
    if not (R/'model-assets.json').exists():
        import shutil
        shutil.copy2(OLD/'model-assets.json',R/'model-assets.json')
    files=['execute_jitter.py','jitter_control.py','run_wave.py','wholehand_side.py','lib/sonic_v11.py']
    hashes={name:sha(R/name) for name in files}
    configs=[]
    for suffix,tau,damping,gain in [('base',0.,2.,.10),('lpf60',.06,2.,.10),('damp3',0.,3.,.10),('servo03',0.,2.,.03)]:
        row={'id':'A_'+suffix,'source_episode':'A000','tau':tau,'damping':damping,'servo_gain':gain,'start':42.,'source_hashes':hashes,
             'role':'diagnostic development trial; select then evaluate other source scenes separately',
             'frozen_source_reference_sha':sha(OLD/'out/A000/reference.npz')}
        configs.append(row)
        new_json(R/'configs'/(row['id']+'.json'),row)
    design={'wave':wave,'frozen':now(),'trials':configs,'max_workers':4,'AS_GiB_per_worker':4,'no_gpu':True,
            'physics_gate':'unchanged wholehand-v2-wristlocal-support',
            'selection':'Require original success gate, identical pretreatment state/input prefix, lower HOLD wrist detrended RMS and arm velocity RMS; report every development failure',
            'scope':'MuJoCo3.2.7 current parameters only; not universal causality or fullARDY'}
    new_json(R/'configs'/(wave+'-design.json'),design)
    record('Finite wave frozen '+json.dumps(design));print(json.dumps(design),flush=True)
elif action=='launch':
    check_rules();resource_probe()
    assert (R/'configs'/(wave+'-design.json')).exists()
    command=['taskset','-c','80-87','/usr/bin/python3','-B',str(R/'run_wave.py'),'run',wave]
    with (R/'logs'/(wave+'-launcher.log')).open('xb') as f:
        p=subprocess.Popen(command,cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    receipt={'wave':wave,'pid':p.pid,'command':command,'cwd':str(R),'started':now(),
             'proc_start_ticks':Path(f'/proc/{p.pid}/stat').read_text().split()[21]}
    new_json(R/'configs'/(wave+'-launch.json'),receipt)
    record('Finite wave launch '+json.dumps(receipt));print(json.dumps(receipt),flush=True)
elif action=='run':
    design=json.loads((R/'configs'/(wave+'-design.json')).read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts=list(pool.map(run_one,[(i%4,row) for i,row in enumerate(design['trials'])]))
    new_json(R/'configs'/(wave+'-done.json'),{'wave':wave,'ended':now(),'receipts':receipts})
    resource_probe()
elif action=='status':
    design=json.loads((R/'configs'/(wave+'-design.json')).read_text())
    rows=[]
    for row in design['trials']:
        receipt=R/'configs'/(row['id']+'-receipt.json')
        log=R/'logs'/(row['id']+'-physics.log')
        text=log.read_text() if log.exists() else ''
        lines=text.splitlines()
        rows.append({'id':row['id'],'receipt':json.loads(receipt.read_text()) if receipt.exists() else None,
                     'tail':lines[-2:]})
    print(json.dumps({'wave':wave,'done':(R/'configs'/(wave+'-done.json')).exists(),'rows':rows}),flush=True)
else:
    raise ValueError(action)
