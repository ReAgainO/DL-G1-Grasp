"""Verify immutable dual archive, checkpoint only own files, open bounded wave3."""
import datetime,hashlib,json,os,shutil,subprocess
from pathlib import Path
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected={str(B/'reports'/f'{T}-wave2-report.md'):'3fcce51462af283c9126a051081ab6cd97f8ae748349328476b5b6d821e00a8e',str(D/'wave2.tar.gz'):'dbe98f87b618ddf698420943a5ed9a734f31e9069986d51bcd22b036c91ccb32'}
for p,h in expected.items():assert sha(p)==h
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert not (W/'wave3-scope.json').exists()
now=datetime.datetime.now().astimezone().isoformat()
scope=dict(time=now,task=T,wave=3,max_physical_episodes=20,max_simulation_seconds=90,max_command_seconds=300,cpu_cores=4,AS_GiB=16,data_budget_GiB=1,gpu=False,shared_writes=False,
 plan='Continue actual-pose Cartesian reference servo, collision-free approach and contact-gated fingers; official SONIC body targets only. Explicitly labelled pelvis-fixture diagnostics allowed, NEVER weld/teleport cube. Compress NEW CSV outputs, do not delete older evidence.')
(W/'wave3-scope.json').write_text(json.dumps(scope,indent=2)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave3_scope='+json.dumps(scope)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE3] '+now+'\n- wave2 report/bundle downloaded to local server_reports/'+T+'; both SHA matched. The earlier transient tar SHA sampled while writer was active is NOT used as final identity; final bundle SHA='+expected[str(D/'wave2.tar.gz')]+'.\n- All wave2 processes exited; no SONIC grasp yet. Task ACTIVE, <=20 new episodes, CPU4/AS16/300s/90s/data1GiB; monitor data before every run, compress new CSV, preserve older evidence.\n')
shutil.copy2(D/'begin_wave3.py',W/'begin_wave3.py')
def git(*args):return subprocess.check_output(['git',*args],cwd=B,text=True)
(W/'wave2-checkpoint-head.before').write_text(git('rev-parse','HEAD'))
(W/'wave2-checkpoint-staged.before').write_text(git('diff','--cached','--name-only'))
idx=git('rev-parse','--git-path','index').strip();shutil.copy2(B/idx,W/'wave2-checkpoint-index.before')
before=git('ls-files','-s');(W/'wave2-checkpoint-blobs.before').write_text(before)
own=['claims/'+T+'/card.txt','claims/'+T+'/rules_seen','logs/'+T+'/steps.md','reports/'+T+'-wave2-report.md']
own += [str(p.relative_to(B)) for p in sorted(W.iterdir()) if p.suffix in ['.py','.sh','.json'] or p.name in ['wave1-archive.sha256','wave2-archive.sha256']]
git('add','-f','--',*own)
git('-c','user.name=codex-hp-745a0dbc-a26f-4c01-add8-7577fca612de','-c','user.email=745a0dbc-a26f-4c01-add8-7577fca612de@worker00039.invalid','commit','--only','-m','Checkpoint 20 bounded ARDY/SONIC grasp launches and native phase generation; no grasp yet, task ACTIVE ('+T+')','--',*own)
after=git('ls-files','-s');(W/'wave2-checkpoint-blobs.after').write_text(after)
def others(t):return {l.split('\t',1)[1]:l.split('\t',1)[0] for l in t.splitlines() if l.split('\t',1)[1] not in own}
assert others(before)==others(after),'Non-owned index changed; no reset performed'
commit=git('rev-parse','HEAD').strip()
env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(k,None)
r=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '第二波20次启动/19次物理步进+1场景失败已退出，双端SHA归档并仅自有路径Git留档；原NPZ与新文本phase clips保留，但SONIC两指抓取仍未完成。继续第三波<=20集、4核AS16GiB、90s仿真300s命令、data1GiB；根部夹具显式标注，物体无焊接/瞬移，身体目标不覆盖SONIC。'],env=env,capture_output=True,text=True,timeout=60)
(L/'wave3-scope-receipt.txt').write_text(r.stdout+r.stderr);assert r.returncode==0
with (L/'steps.md').open('a') as f:f.write('- own checkpoint commit='+commit+'; other indexed blobs unchanged; no push.\n'+r.stdout+r.stderr)
print(json.dumps(dict(commit=commit,scope=scope,receipt=r.stdout+r.stderr),indent=2))
