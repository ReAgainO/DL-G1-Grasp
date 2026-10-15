"""Verify both archives, preserve shared Git index, renew a bounded CPU wave."""
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
args = p.parse_args()
B = Path('/home/group4/group4_dasc7606c')
T = '20261006-093203-codex-6385a841'
SID = '745a0dbc-a26f-4c01-add8-7577fca612de'
D = Path('/data/group4')/T
W = B/'work'/T
L = B/'logs'/T
rp = B/'reports'/f'{T}-wave4-report.md'
bundle = D/'wave4.tar.gz'
assert sha(rp) == args.local_report_sha == '71e2a8934628025ff71de7974c726b4129fac3e851d48608e51aa582b1215c4e'
assert sha(bundle) == args.local_bundle_sha == 'a0d95f19604dc31c715767f887ede81b0f8fd4a65c07e1a7c0ed76d85bebce31'
assert sha(B/'AGENTS.md') == '9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert not (W/'wave5-scope.json').exists() and not (D/'active_cpu_wave.json').exists()
assert not (D/'wave5-launches.jsonl').exists()
processes = subprocess.check_output(['ps','-eo','pid,args'], text=True).splitlines()
assert len(processes) < 20000
assert not any(str(D) in line and any(name in line for name in ['sonic_grasp.py','render_verified_replay.py']) for line in processes), 'Prior own worker still active'
actual = int(subprocess.check_output(['du','-sb',str(D)], text=True).split()[0])
assert actual + 20*12*1024**2 + 160*1024**2 < 2*1024**3
assert shutil.disk_usage(D).free > 30*1024**3
now = datetime.datetime.now().astimezone().isoformat()
scope = dict(task=T,wave=5,time=now,max_physical_script_launches=20,
             max_simulation_seconds=90,max_command_seconds=300,cpu_cores=4,
             AS_GiB=16,data_budget_GiB=2,gpu=False,shared_source_writes=False,
             plan='First same-source ARDY ON/OFF and positive replication; audit per-body robot/table contact. Test table front .245 vs .23, preserving cube pose/mass/friction, complete broad tabletop support and back edge. This is an environment placement counterfactual, not an algorithm claim. Then table avoidance/capture and free-base validation; official SONIC body targets, independent fingers only.',
             prior_wave='20 launches exited;2 successful fixed-base3.2.7 repeated configurations;3.14.0 and free-base grasp failed. No full Track4/real robot completion claim.',
             launch_guard='reserve_cpu_trial.py: own atomic20-slot ledger, startup failures count; isolated10 rejection-branch tests passed',
             estimated_data_bytes_before=actual)
(W/'wave5-scope.json').write_text(json.dumps(scope,indent=2)+'\n')
(D/'active_cpu_wave.json').write_text(json.dumps(scope,indent=2)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:
    f.write('wave5_scope='+json.dumps(scope)+'\n')
with (B/'claims'/T/'rules_seen_after').open('a') as f:
    f.write(sha(B/'AGENTS.md')+'  '+str(B/'AGENTS.md')+'\n')
with (L/'steps.md').open('a') as f:
    f.write(f'\n## [WAVE5 RENEWAL] {now}\n-Local and server report SHA='+args.local_report_sha+'; bundle SHA='+args.local_bundle_sha+'; independently computed locally after SCP. No running own physical/render worker.\n-20 previous physical launches exited, strict fixed-base3.2.7 two passes; not full Track4. Renew <=20 CPU launches,4cores/AS16GiB/300s/90s, cumulative2GiB task storage, no GPU and no KIMODO.\n-First matched-source ARDY paired controls, then geometric table contact audit and free-base. Environment placement changes labelled; no collision removal/object weld/teleport/forces.\n')
env = os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:
    env.pop(key,None)
receipt = subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
    '第四波20次启动退出；MuJoCo3.2.7固定pelvis同配置两次成功，HOLD95.519mm/双指/滑移3.567mm/释放通过；3.14.0及两版自由底座抓取仍失败，不标Track4完成。六段报告和原始包双端SHA相同，录像源于保存轨迹零物理步进。第五波<=20启动4核AS16/300s/90s/累计data2GiB，先同源码ARDY配对、初始腕桌干扰与自由底座；只写本TASKID、不碰KIMODO/共享源。'],env=env,capture_output=True,text=True,timeout=60)
(L/'wave5-scope-receipt.txt').write_text(receipt.stdout+receipt.stderr)
assert receipt.returncode == 0, (receipt.returncode,receipt.stdout,receipt.stderr)
with (L/'steps.md').open('a') as f:
    f.write(receipt.stdout+receipt.stderr)
for src in D.iterdir():
    if src.is_file() and src.suffix in {'.py','.sh'}:
        shutil.copy2(src,W/src.name)
git_env = env.copy()
identity = 'codex-hp-'+SID
email = SID+'@worker00039.invalid'
for prefix in ['GIT_AUTHOR','GIT_COMMITTER']:
    git_env[prefix+'_NAME'] = identity
    git_env[prefix+'_EMAIL'] = email
def git(*items):
    return subprocess.check_output(['git',*items],cwd=B,env=git_env,text=True)
head_before = git('rev-parse','HEAD').strip()
(W/'wave4-checkpoint-head.before').write_text(head_before+'\n')
(W/'wave4-checkpoint-staged.before').write_text(git('diff','--cached','--name-only'))
index_path = Path(git('rev-parse','--git-path','index').strip())
if not index_path.is_absolute():
    index_path = B/index_path
shutil.copy2(index_path,W/'wave4-checkpoint-index.before')
before = git('ls-files','-s')
(W/'wave4-checkpoint-blobs.before').write_text(before)
own = [f'claims/{T}/card.txt',f'claims/{T}/rules_seen',f'claims/{T}/rules_seen_after',
       f'logs/{T}/steps.md',f'logs/{T}/wave5-scope-receipt.txt',f'reports/{T}-wave4-report.md']
own += [str(file.relative_to(B)) for file in sorted(W.iterdir())
        if file.suffix in {'.py','.sh','.json'} or file.name.endswith('-archive.sha256')]
git('add','-f','--',*own)
git('commit','--only','-m',f'Checkpoint ARDY SONIC wave4: repeated fixed-base pass; free-base/version limits retained; ACTIVE ({T})','--',*own)
after = git('ls-files','-s')
(W/'wave4-checkpoint-blobs.after').write_text(after)
def others(text):
    return {line.split('\t',1)[1]:line.split('\t',1)[0] for line in text.splitlines()
            if line.split('\t',1)[1] not in own}
assert others(before) == others(after), 'Non-owned staged entries changed; do not reset'
commit = git('rev-parse','HEAD').strip()
changed = git('diff-tree','--no-commit-id','--name-only','-r',commit).splitlines()
assert all(path in own for path in changed), 'Unexpected commit path'
result = dict(commit=commit,head_before=head_before,other_index_blobs_preserved=True,
              report_sha256=args.local_report_sha,bundle_sha256=args.local_bundle_sha,
              journal_receipt=receipt.stdout,scope=scope,no_push=True,
              commit_cutoff='includes scope/journal receipt; this postcommit verification note is deliberately next incremental checkpoint')
(L/'wave4-git-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
with (L/'steps.md').open('a') as f:
    f.write('-Git own checkpoint='+commit+'; other staged blobs preserved, no push. Receipt and this tail are next incremental checkpoint, not claimed in already sealed wave4 tar.\n')
print(json.dumps(result,indent=2))
