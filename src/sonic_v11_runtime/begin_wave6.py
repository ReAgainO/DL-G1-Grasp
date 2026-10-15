"""Verify wave5 dual archive, preserve shared index, deploy a unique entry."""
import argparse
import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path
from wave4_records import sha

p = argparse.ArgumentParser()
p.add_argument('--local-report-sha', required=True)
p.add_argument('--local-bundle-sha', required=True)
a = p.parse_args()
B = Path('/home/group4/group4_dasc7606c')
T = '20261006-093203-codex-6385a841'
SID = '745a0dbc-a26f-4c01-add8-7577fca612de'
D = Path('/data/group4') / T
W = B / 'work' / T
L = B / 'logs' / T
rp = B / 'reports' / f'{T}-wave5-report.md'
assert sha(rp) == a.local_report_sha == '31c2c60184776df3b4fd25767ccd47c1d46207d317465d3f0df31d758f635192'
assert sha(D/'wave5.tar.gz') == a.local_bundle_sha == '6cb6bec55e89be1f12f33913f9195c3db2f112968afaed79975865fe5ed341f4'
assert sha(B/'AGENTS.md') == '9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert SID in (B/'claims'/T/'card.txt').read_text()
assert not (B/'claims'/T/'done.txt').exists()
assert not (W/'wave6-scope.json').exists() and not (D/'wave6-launches.jsonl').exists()
oldscope = json.loads((D/'active_cpu_wave.json').read_text())
assert oldscope['wave'] == 5
assert len((D/'wave5-launches.jsonl').read_text().splitlines()) == 20
processes = subprocess.check_output(['ps','-eo','pid,args'], text=True).splitlines()
assert len(processes) < 20000
assert not any(str(D) in row and any(x in row for x in ['sonic_grasp.py','render_verified_replay.py']) for row in processes)
actual = int(subprocess.check_output(['du','-sb',str(D)], text=True).split()[0])
assert actual + 20*16*1024**2 + 320*1024**2 < 3*1024**3
assert shutil.disk_usage(D).free > 30*1024**3
entry = B / f'ardy-grasp-run-{T}.sh'
assert not entry.exists() and not entry.is_symlink()
now = datetime.datetime.now().astimezone().isoformat()
scope = dict(task=T,wave=6,time=now,max_physical_script_launches=20,
    max_simulation_seconds=90,max_command_seconds=300,cpu_cores=4,AS_GiB=16,
    data_budget_GiB=3,gpu=False,shared_source_writes='unique root launcher; vendor source unchanged',
    plan='Original solver contacts identify SETTLE/APPROACH right wrist-table collision. Compare labelled neutral shoulder +.1rad initialization AND SONIC input stance; retain official body decoder motor targets. Audit actual 500Hz speed/limits/full-task table contact. Then contact-continuous placing and fresh generated NPZ/interaction metrics.',
    storage_change='Renew cumulative2->3GiB to retain old raw records/archives plus <=20 new launches/next archive. No deletion or shared downloads; /home only bounded texts.',
    user_authorization='User: 不用限制在独立任务目录中，有改进的地方可以直接上传至服务器. Direct deployment allowed; no teammate overwrite/KIMODO/system changes.',
    estimated_data_bytes_before=actual,prior_wave='20 exited; legacy7/actual-table5/controlled-placing0; not full Track4')
(W/'wave6-scope.json').write_text(json.dumps(scope,indent=2)+'\n')
shutil.copy2(D/'active_cpu_wave.json',W/'wave5-active-scope.before.json')
(D/'active_cpu_wave.json').write_text(json.dumps(scope,indent=2)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:
    f.write('wave6_scope='+json.dumps(scope,ensure_ascii=False)+'\n')
shutil.copy2(D/'ardy-server-entry.sh',entry)
assert sha(entry) == sha(D/'ardy-server-entry.sh')
with (B/'claims'/T/'rules_seen_after').open('a') as f:
    f.write(sha(B/'AGENTS.md')+'  '+str(B/'AGENTS.md')+'\n')
with (L/'steps.md').open('a') as f:
    f.write(f'\n## [WAVE6 RENEWAL / DIRECT DEPLOYMENT] {now}\n-User permits direct server uploads; new unique shared-root entry='+str(entry)+'; no existing teammate/vendor file overwritten.\n-Wave5 report/bundle independently downloaded and hashed locally; matching '+a.local_report_sha+' / '+a.local_bundle_sha+'.\n-Renew <=20 launches,4CPU/AS16/300s/90s; cumulative budget3GiB explicitly preserves prior2GiB evidence. No GPU/new environment/real robot/public service.\n-Initial clearance preflight zero steps, 2425 original solver contact rows; right wrist SETTLE .252-2s / APPROACH2.002-4.636s max44.275N. Candidate +.1rad shoulders geometric-only; not an implemented path or balance success.\n')
env = os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:
    env.pop(key,None)
receipt = subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
    '第五波20次退出并完整双端SHA归档：legacy7/确实落桌5/受控放置0；自由3.2.7同配置2/2，初始腕桌碰撞/实际峰速仍未解，目标ACTIVE。用户允许直接部署服务器；新增本任务命名根启动器不覆盖队友。第六波<=20 CPU启动4核AS16/300s/90s，累计data显式更新3GiB保留旧证据；先姿态/实际运动与碰撞审计，两版本官方SONIC身体输出不覆盖。'],env=env,capture_output=True,text=True,timeout=60)
(L/'wave6-scope-receipt.txt').write_text(receipt.stdout+receipt.stderr)
assert receipt.returncode == 0, (receipt.returncode,receipt.stdout,receipt.stderr)
with (L/'steps.md').open('a') as f:
    f.write(receipt.stdout+receipt.stderr)
for src in D.iterdir():
    if src.is_file() and src.suffix in {'.py','.sh'}:
        shutil.copy2(src,W/src.name)
shutil.copy2(D/'wave5-summary.json',W/'wave5-summary.json')
git_env = env.copy()
for prefix in ['GIT_AUTHOR','GIT_COMMITTER']:
    git_env[prefix+'_NAME'] = 'codex-hp-'+SID
    git_env[prefix+'_EMAIL'] = SID+'@worker00039.invalid'
def git(*items):
    return subprocess.check_output(['git','-c','gc.auto=0',*items],cwd=B,env=git_env,text=True)
before_head = git('rev-parse','HEAD').strip()
(W/'wave5-checkpoint-head.before').write_text(before_head+'\n')
(W/'wave5-checkpoint-staged.before').write_text(git('diff','--cached','--name-only'))
index = Path(git('rev-parse','--git-path','index').strip())
shutil.copy2(index if index.is_absolute() else B/index,W/'wave5-checkpoint-index.before')
before = git('ls-files','-s')
(W/'wave5-checkpoint-blobs.before').write_text(before)
own = [f'claims/{T}/card.txt',f'claims/{T}/rules_seen',f'claims/{T}/rules_seen_after',
       f'logs/{T}/steps.md',f'logs/{T}/wave6-scope-receipt.txt',f'reports/{T}-wave5-report.md',entry.name]
own += [str(file.relative_to(B)) for file in sorted(W.iterdir())
        if file.suffix in {'.py','.sh','.json'} or file.name.endswith('-archive.sha256')]
git('add','-f','--',*own)
git('commit','--only','-m',f'ARDY SONIC wave5: audited free-base grasp, table/floor erratum; direct server entry and wave6 ACTIVE ({T})','--',*own)
after = git('ls-files','-s')
(W/'wave5-checkpoint-blobs.after').write_text(after)
def others(text):
    return {row.split('\t',1)[1]:row.split('\t',1)[0] for row in text.splitlines()
            if row.split('\t',1)[1] not in own}
assert others(before) == others(after), 'Other staged blobs changed; do not reset'
commit = git('rev-parse','HEAD').strip()
changed = git('diff-tree','--no-commit-id','--name-only','-r',commit).splitlines()
assert all(path in own for path in changed)
assert git('log','-1','--format=%ae').strip() == SID+'@worker00039.invalid'
answer = dict(commit=commit,head_before=before_head,other_index_blobs_preserved=True,
    report_sha256=a.local_report_sha,bundle_sha256=a.local_bundle_sha,
    journal_receipt=receipt.stdout,scope=scope,shared_entry=str(entry),shared_entry_sha256=sha(entry),
    no_push=True,task_active=True,cutoff='Postcommit receipt/tail deliberately next incremental checkpoint, not part of sealed wave5 bundle')
(L/'wave5-git-receipt.json').write_text(json.dumps(answer,indent=2)+'\n')
with (L/'steps.md').open('a') as f:
    f.write('-Own checkpoint='+commit+'; other staged blobs preserved, no push. Receipt/tail are next incremental checkpoint.\n')
print(json.dumps(answer,indent=2))
