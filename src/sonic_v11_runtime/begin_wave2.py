"""Verify dual checkpoint, explicit own Git snapshot, then authorize next bounded wave."""
import datetime,hashlib,json,os,shutil,subprocess
from pathlib import Path
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected={'reports/'+T+'-wave1-report.md':'fc54955853b712291f95f15385cca601d82134a64e79afbc0429028ce1397f4c',
          str(D/'wave1.tar.gz'):'fe6900bdd264ae419f197d044dcceabf3f6caef2938cdf46caadc19f3237dc30'}
for p,h in expected.items():assert sha(B/p if not p.startswith('/') else p)==h
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert not (W/'wave2-scope.json').exists()
now=datetime.datetime.now().astimezone().isoformat()
scope=dict(time=now,task=T,wave=2,max_physical_episodes=20,max_simulation_seconds=90,max_command_seconds=300,
           cpu_cores=4,AS_GiB=16,data_budget_GiB=1,gpu=False,shared_writes=False,
           plan='ARDY reference task-space retargeting/SONIC full body; separate contact-gated fingers; calibrated geometry explicitly labelled')
(W/'wave2-scope.json').write_text(json.dumps(scope,indent=2)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave2_scope='+json.dumps(scope,ensure_ascii=False)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE2] '+now+'\n- wave1 report/bundle downloaded to local server_reports/'+T+' and SHA matched.\n- Task remains ACTIVE. New bounded wave <=20 physical episodes; CPU4 AS16GiB, no GPU/services/shared edits.\n')
shutil.copy2(D/'begin_wave2.py',W/'begin_wave2.py')
def git(*args):return subprocess.check_output(['git',*args],cwd=B,text=True)
(W/'checkpoint-head.before').write_text(git('rev-parse','HEAD'))
(W/'checkpoint-staged.before').write_text(git('diff','--cached','--name-only'))
idx=git('rev-parse','--git-path','index').strip();shutil.copy2(B/idx,W/'checkpoint-index.before')
before=git('ls-files','-s');(W/'checkpoint-index-blobs.before').write_text(before)
own=['claims/'+T+'/card.txt','claims/'+T+'/rules_seen','logs/'+T+'/steps.md','reports/'+T+'-wave1-report.md']
own += [str(p.relative_to(B)) for p in sorted(W.iterdir()) if p.suffix in ['.py','.sh','.json'] or p.name=='wave1-archive.sha256']
git('add','-f','--',*own)
git('-c','user.name=codex-hp-745a0dbc-a26f-4c01-add8-7577fca612de','-c','user.email=745a0dbc-a26f-4c01-add8-7577fca612de@worker00039.invalid',
    'commit','--only','-m','Checkpoint official SONIC CPU integration and original ARDY NPZ physical tracking; task ACTIVE ('+T+')','--',*own)
after=git('ls-files','-s');(W/'checkpoint-index-blobs.after').write_text(after)
def others(s):return {l.split('\t',1)[1]:l.split('\t',1)[0] for l in s.splitlines() if l.split('\t',1)[1] not in own}
assert others(before)==others(after),'Non-owned index changed; no reset performed'
commit=git('rev-parse','HEAD').strip()
env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(k,None)
cmd=['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
     '20集第一波已退出并双端SHA归档；官方SONIC1751/994接通，原始NPZ25fps对拍；原始动作慢速RMS.07536rad但无抓取。继续第二波<=20集4核AS16GiB90s仿真300s命令，只写自有任务；身体29通道不覆盖SONIC。']
r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=60)
(L/'wave2-scope-receipt.txt').write_text(r.stdout+r.stderr);assert r.returncode==0
with (L/'steps.md').open('a') as f:f.write('- own checkpoint commit='+commit+'; non-owned index blobs unchanged, no push.\n'+r.stdout)
print(json.dumps(dict(commit=commit,scope=scope,receipt=r.stdout),indent=2))
