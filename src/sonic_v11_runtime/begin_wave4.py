"""Verify third-wave archive, own-path Git checkpoint, renew bounded scope."""
import datetime,hashlib,json,os,shutil,subprocess
from pathlib import Path
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
expected={str(B/'reports'/f'{T}-wave3-report.md'):'045b5dd7236c36f7d5f996e176cf2b2bc9802e9e85ee46f8e38ca1fe34e1eea9',str(D/'wave3.tar.gz'):'45fca6860ea804aec5c0d06b6b0fe00692ea80d7ec05d347d40f4f4ee8f339dd'}
for p,h in expected.items():assert sha(p)==h
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert not (W/'wave4-scope.json').exists()
assert shutil.disk_usage(D).free>30*1024**3
now=datetime.datetime.now().astimezone().isoformat()
scope=dict(time=now,task=T,wave=4,max_physical_script_launches=20,max_simulation_seconds=90,max_command_seconds=300,cpu_cores=4,AS_GiB=16,data_budget_GiB=2,gpu=False,shared_writes=False,
 plan='Keep captured separate finger commands and actual wrist-frame lift. Compare independent right-arm damping only after capture; no manual body targets, no object weld/teleport/forces. Two MuJoCo versions, repetitions and negative controls, then free-base validation. Inspect official inertia parameters before any derived-model consistency test.',
 disk_scope_change='Prior1GiB remains respected through completed wave3 archive. Explicitly renew cumulative self-task budget to2GiB to preserve prior raw evidence plus <=20 new episodes and next archive; data12TiB free, no deletion or shared downloads.')
(W/'wave4-scope.json').write_text(json.dumps(scope,indent=2)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave4_scope='+json.dumps(scope)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE4] '+now+'\n- wave3 report and bundle verified on local and server with identical SHA; all20 launches exited, strict0success, sustained grip/HOLD42.941mm is partial progress only. Source snapshot missing0.\n- Renew <=20 CPU launches,4cores/AS16/300s/90s; explicit cumulative self data budget2GiB before growth (data12TiB free); preserve prior archives and raw evidence.\n- Body motor positions remain official SONIC; optional independently scaled damping is an actuator adaptation, not factory SONIC. No scripted body target bypass.\n')
shutil.copy2(D/'begin_wave4.py',W/'begin_wave4.py')
def git(*args):return subprocess.check_output(['git',*args],cwd=B,text=True)
(W/'wave3-checkpoint-head.before').write_text(git('rev-parse','HEAD'))
(W/'wave3-checkpoint-staged.before').write_text(git('diff','--cached','--name-only'))
idx=git('rev-parse','--git-path','index').strip();shutil.copy2(B/idx,W/'wave3-checkpoint-index.before')
before=git('ls-files','-s');(W/'wave3-checkpoint-blobs.before').write_text(before)
own=['claims/'+T+'/card.txt','claims/'+T+'/rules_seen','logs/'+T+'/steps.md','reports/'+T+'-wave3-report.md']
own += [str(p.relative_to(B)) for p in sorted(W.iterdir()) if p.suffix in ['.py','.sh','.json'] or p.name in ['wave1-archive.sha256','wave2-archive.sha256','wave3-archive.sha256']]
git('add','-f','--',*own)
git('-c','user.name=codex-hp-745a0dbc-a26f-4c01-add8-7577fca612de','-c','user.email=745a0dbc-a26f-4c01-add8-7577fca612de@worker00039.invalid','commit','--only','-m','Checkpoint20 ARDY SONIC physical trials: sustained grasp but42.9mm HOLD below70mm; ACTIVE ('+T+')','--',*own)
after=git('ls-files','-s');(W/'wave3-checkpoint-blobs.after').write_text(after)
def others(t):return {l.split('\t',1)[1]:l.split('\t',1)[0] for l in t.splitlines() if l.split('\t',1)[1] not in own}
assert others(before)==others(after),'Non-owned index changed; do not reset'
commit=git('rev-parse','HEAD').strip();env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(k,None)
p=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '第三波20次物理启动已退出并双端SHA/Git仅自有路径归档，持续双指夹持但HOLD最低42.941mm未达70mm，不标完成。继续第四波<=20启动、4核AS16/90s/300s，自有累计data预算显式更新2GiB（保留所有旧证据、data12TiB空余）。独立阻尼适配不改变官方SONIC身体目标；固定pelvis不冒充平衡，物体永不焊接/瞬移/外力。'],env=env,capture_output=True,text=True,timeout=60)
(L/'wave4-scope-receipt.txt').write_text(p.stdout+p.stderr);assert p.returncode==0
with (L/'steps.md').open('a') as f:f.write('- own Git commit='+commit+'; other index blobs preserved, no push.\n'+p.stdout+p.stderr)
print(json.dumps(dict(commit=commit,scope=scope,receipt=p.stdout+p.stderr),indent=2))
