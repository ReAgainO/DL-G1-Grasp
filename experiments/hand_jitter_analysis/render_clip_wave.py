"""Bounded four-job true-state replay with a task-wide no-physics launch guard."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,fcntl
from concurrent.futures import ThreadPoolExecutor
from launch_safe import active
R=Path(__file__).resolve().parent;B=Path('/home/group4/group4_dasc7606c')
PY='/data/group4/20261004-205550-qoder-1280b420/env/bin/python'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
env=os.environ.copy();env.update({'MUJOCO_GL':'osmesa','PYOPENGL_PLATFORM':'osmesa','LP_NUM_THREADS':'2',
    'LD_LIBRARY_PATH':'/data/group4/20261008-220500-codex-6c40bf04/lib','TMPDIR':str(R/'tmp'),'XDG_CACHE_HOME':str(R/'tmp/cache'),
    'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
action=sys.argv[1]
def job(pair):
    slot,episode=pair
    command=['timeout','--kill-after=5','580','taskset','-c',f'{80+2*slot},{81+2*slot}',PY,'-B',str(R/'render_clip.py'),episode]
    with (R/'logs'/(episode+'-render25clip.log')).open('xb') as f:
        p=subprocess.Popen(command,cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT);rc=p.wait()
    receipt={'id':episode,'rc':rc,'pid':p.pid,'command':command,'ended':datetime.datetime.now().astimezone().isoformat()}
    replay=R/'out'/episode/'replay25clip/replay.json'
    if replay.exists():receipt['replay']=json.loads(replay.read_text())
    with (R/'configs'/(episode+'-render25clip-receipt.json')).open('x') as f:json.dump(receipt,f,indent=2)
    return receipt
if action=='launch':
    ids=sys.argv[2:];assert 1<=len(ids)<=4 and len(ids)==len(set(ids))
    assert all(i.replace('_','').isalnum() for i in ids)
    with (R/'configs/launch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        processes=[row for row in active() if row['pid']!=os.getpid()];assert not processes,processes
        assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
        resources=subprocess.run(['df','-h','/home','/data','/tmp'],capture_output=True,text=True,check=True,timeout=20).stdout
        memory=subprocess.run(['free','-g'],capture_output=True,text=True,check=True,timeout=20).stdout
        design={'ids':ids,'renderer_sha':sha(R/'render_clip.py'),'runner_sha':sha(__file__),'max_workers':4,'command_limit_s':580}
        with (R/'configs/render25clip-design.json').open('x') as f:json.dump(design,f,indent=2)
        command=['taskset','-c','80-87','/usr/bin/python3','-B',str(R/'render_clip_wave.py'),'run']
        with (R/'logs/render25clip-launcher.log').open('xb') as f:
            p=subprocess.Popen(command,cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
        receipt={'pid':p.pid,'ticks':Path(f'/proc/{p.pid}/stat').read_text().split()[21],'command':command,'cwd':str(R),'started':datetime.datetime.now().astimezone().isoformat()}
        with (R/'configs/render25clip-launch.json').open('x') as f:json.dump(receipt,f,indent=2)
        with (B/'logs'/R.name/'steps.md').open('a') as f:
            f.write('\n- Renderer resource probe\n'+resources+memory+'\n'+json.dumps({k:Path('/proc/pressure',k).read_text() for k in ['cpu','memory','io']})+'\n- '+json.dumps(receipt)+'\n')
        print(json.dumps(receipt))
elif action=='run':
    design=json.loads((R/'configs/render25clip-design.json').read_text());assert sha(R/'render_clip.py')==design['renderer_sha'] and sha(__file__)==design['runner_sha']
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(job,enumerate(design['ids'])))
    with (R/'configs/render25clip-done.json').open('x') as f:json.dump({'rows':rows},f,indent=2)
    with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- Render wave terminal '+json.dumps([{k:r[k] for k in ['id','rc','pid','ended']} for r in rows])+'\n')
else:raise ValueError(action)
