"""Run only bounded experiments within this task and retain each result/failure."""
from pathlib import Path
import datetime,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parent
TASK=ROOT.name
B=Path('/home/group4/group4_dasc7606c')
PY='/data/group4/20261004-205550-qoder-1280b420/env/bin/python'
name=sys.argv[1]
assert name.replace('_','').replace('-','').isalnum()
args=sys.argv[2:];script='wholehand_side.py'
if args and args[0]=='--script':
 script=args[1];args=args[2:]
 assert script in ['execute_side.py','wholehand_side.py']
env=os.environ.copy()
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','PYTHONDONTWRITEBYTECODE']:env[k]='1'
env['TMPDIR']=str(ROOT/'tmp')
command=['timeout','900','taskset','-c','82,83' if script=='execute_side.py' and 'negative' not in name else '80,81',PY,'-B',str(ROOT/script)]+args
record={'started':datetime.datetime.now().astimezone().isoformat(),'command':command}
log=ROOT/'logs'/f'{name}.log'
with log.open('x') as f:
 result=subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
record.update(returncode=result.returncode,finished=datetime.datetime.now().astimezone().isoformat(),log=str(log))
(ROOT/'logs'/f'{name}.receipt.json').write_text(json.dumps(record,indent=2))
with (B/'logs'/TASK/'steps.md').open('a') as f:
 f.write('\n## Bounded run '+name+'\n'+json.dumps(record,indent=2)+'\n')
print(json.dumps(record));print(log.read_text()[-10000:])
raise SystemExit(result.returncode)
