"""Own-path only checkpoint after independent local archive verification."""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from wave4_records import sha

p=argparse.ArgumentParser()
p.add_argument('--local-report-sha',required=True)
p.add_argument('--local-bundle-sha',required=True)
p.add_argument('--local-summary-sha',required=True)
a=p.parse_args()
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
SID='745a0dbc-a26f-4c01-add8-7577fca612de'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
report=B/'reports'/f'{T}-wave6-progress2-report.md'
assert sha(report)==a.local_report_sha=='0386dcf44ad8dc57e49e85d1c180a5e615f10533021958de8e7bd794069bbc4d'
assert sha(D/'wave6-progress2.tar.gz')==a.local_bundle_sha=='489cfb66bc3a17f73453fe2dbb2f17abff327a1af5b07893ffc79c082f5678a6'
assert sha(D/'wave6-progress2.json')==a.local_summary_sha=='873144823d03b54c1d350e387073d771dc8b43a1f21e1627c723b985f4da543a'
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert SID in (B/'claims'/T/'card.txt').read_text() and not (B/'claims'/T/'done.txt').exists()
receipt_path=L/'wave6-progress2-git-receipt.json'
note_path=L/'wave6-progress2-journal-receipt.txt'
assert not receipt_path.exists() and not note_path.exists()
for path in D.iterdir():
    if path.is_file() and path.suffix in {'.py','.sh'}:shutil.copy2(path,W/path.name)
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:
    env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
    '用户允许直接服务器部署，根入口已支持status/profile-check/选NPZ执行；第六波13启动全部退出，严格成功0，仍余7，目标ACTIVE。旧near两版0.2参考+抬腕转向全过程碰桌0N、右臂峰速1.348/1.345rad/s但LIFT脱手；默认1509帧回归8类数组完全相同。reach_s43实际进入SONIC且输出改变，两版碰桌4.466/2.691N并抓持失败，未称泛化成功。13例原始数据/源/报告双端SHA已核，不覆盖队友vendor或KIMODO。'],
    cwd=B,env=env,capture_output=True,text=True,timeout=60)
note_path.write_text(note.stdout+note.stderr)
assert note.returncode==0,(note.returncode,note.stdout,note.stderr)
match=re.search(r'OK journal #(\d+)',note.stdout+note.stderr)
assert match,'No successful journal receipt body'
now=datetime.datetime.now().astimezone().isoformat()
with (L/'steps.md').open('a') as stream:
    stream.write(f'\n## [WAVE6 PROGRESS2 DUAL ARCHIVE / GIT] {now}\n-Local report/bundle/summary independently hashed '+a.local_report_sha+' / '+a.local_bundle_sha+' / '+a.local_summary_sha+'.\n'+note.stdout+note.stderr)
git_env=env.copy()
for prefix in ['GIT_AUTHOR','GIT_COMMITTER']:
    git_env[prefix+'_NAME']='codex-hp-'+SID
    git_env[prefix+'_EMAIL']=SID+'@worker00039.invalid'
def git(*items):
    return subprocess.check_output(['git','-c','gc.auto=0',*items],cwd=B,env=git_env,text=True)
before_head=git('rev-parse','HEAD').strip()
(W/'wave6-progress2-head.before').write_text(before_head+'\n')
(W/'wave6-progress2-staged.before').write_text(git('diff','--cached','--name-only'))
index=Path(git('rev-parse','--git-path','index').strip())
shutil.copy2(index if index.is_absolute() else B/index,W/'wave6-progress2-index.before')
before=git('ls-files','-s');(W/'wave6-progress2-blobs.before').write_text(before)
entry=B/f'ardy-grasp-run-{T}.sh'
own=[str(entry.relative_to(B)),str(report.relative_to(B)),f'reports/{T}-wave6-progress1-report.md',
    f'claims/{T}/card.txt',f'claims/{T}/rules_seen',f'claims/{T}/rules_seen_after',
    f'logs/{T}/steps.md',str(note_path.relative_to(B)),f'logs/{T}/wave5-git-receipt.json']
own += [str(path.relative_to(B)) for path in sorted(W.iterdir())
    if path.suffix in {'.py','.sh','.json'} or path.name.endswith('-archive.sha256')]
assert len(set(own))==len(own)
git('add','-f','--',*own)
git('commit','--only','-m',f'ARDY wave6 partial13: zero-table-contact old-input route, verified generated NPZ selection; grip failures retained, ACTIVE ({T})','--',*own)
after=git('ls-files','-s');(W/'wave6-progress2-blobs.after').write_text(after)
def others(text):
    return {row.split('\t',1)[1]:row.split('\t',1)[0] for row in text.splitlines()
        if row.split('\t',1)[1] not in own}
assert others(before)==others(after),'Other staged blobs changed; do not reset'
commit=git('rev-parse','HEAD').strip()
changed=git('diff-tree','--no-commit-id','--name-only','-r',commit).splitlines()
assert all(path in own for path in changed)
assert git('log','-1','--format=%ae').strip()==SID+'@worker00039.invalid'
git('ls-files','--error-unmatch','--',*own)
checks={}
for path in [entry,report,W/'sonic_grasp.py',W/'motion_profile.py',W/'clearance_approach.py',W/'wave6_records.py']:
    relative=str(path.relative_to(B))
    saved=subprocess.check_output(['git','-c','gc.auto=0','show','HEAD:'+relative],cwd=B,env=git_env)
    digest=hashlib.sha256(saved).hexdigest()
    assert digest==sha(path)
    checks[relative]=dict(sha256=digest,tree=git('ls-tree','HEAD','--',relative).strip(),
        filesystem_mode=oct(path.stat().st_mode&0o777))
answer=dict(commit=commit,head_before=before_head,other_index_blobs_preserved=True,
    changed_paths=changed,verified_blobs=checks,local_report_sha256=a.local_report_sha,
    local_bundle_sha256=a.local_bundle_sha,local_summary_sha256=a.local_summary_sha,
    journal_number=int(match.group(1)),journal_receipt=note.stdout+note.stderr,no_push=True,
    task_active=True,remaining_wave6_launches=7,
    cutoff='New receipt and postcommit steps tail deliberately next incremental snapshot; not part of sealed progress2 bundle')
receipt_path.write_text(json.dumps(answer,indent=2)+'\n')
with (L/'steps.md').open('a') as stream:
    stream.write('-Own-path checkpoint='+commit+'; other indexed blobs preserved, key blobs/modes verified; no push. Postcommit receipt/tail not claimed inside earlier sealed archive.\n')
print(json.dumps(answer,indent=2))
