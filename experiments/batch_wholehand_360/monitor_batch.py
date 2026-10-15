"""Own-task ten-sample status listener, maximum540s, no new experiments."""
import os,resource
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
from pathlib import Path
import subprocess,json,time,datetime
R=Path(__file__).resolve().parent
B=Path('/home/group4/group4_dasc7606c')
RULES='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
started=time.monotonic()
with (B/'logs'/R.name/'steps.md').open('a') as stream:
    stream.write('\n- '+datetime.datetime.now().astimezone().isoformat()+' START bounded10-sample status listener; wall<=540s; own2core affinity; no simulation mutation\n')
for number in range(10):
    if time.monotonic()-started>490:break
    proc=subprocess.run(['timeout','45','/usr/bin/python3','-B',str(R/'status_batch.py'),'--compact'],
                        capture_output=True,text=True,timeout=50)
    print(proc.stdout.strip(),flush=True)
    if proc.returncode:
        print(json.dumps({'listener_error_rc':proc.returncode,'stderr':proc.stderr}),flush=True)
        raise SystemExit(proc.returncode)
    status=json.loads(proc.stdout)
    if status['ended'] or status['errors'] or status['rules_sha']!=RULES or status['data_GiB']>19:
        break
    if number<9:time.sleep(49)
with (B/'logs'/R.name/'steps.md').open('a') as stream:
    stream.write('\n- '+datetime.datetime.now().astimezone().isoformat()+' END bounded status listener elapsed='+str(time.monotonic()-started)+'s\n')
