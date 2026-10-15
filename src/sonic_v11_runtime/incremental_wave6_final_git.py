"""Seal own-path Git after independently verified wave6 full20 transport."""
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
for key in ['report','bundle','summary']:
    p.add_argument('--local-'+key+'-sha',required=True)
a=p.parse_args()
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
SID='745a0dbc-a26f-4c01-add8-7577fca612de'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
report=B/'reports'/f'{T}-wave6-report.md'
expected={
 'report':(report,'03fe1b076da586c935802bdd249c0d98c6a14c91cc9496181ae4d33c9cab0e34'),
 'bundle':(D/'wave6.tar.gz','cc8cb47d5d0983a907974948ba762cb90c1738d308787d326f582d326c8d32fe'),
 'summary':(D/'wave6-summary.json','0b68d7dde0fb2e3b64e19c395200652efd148d0bf13403c1a9100c785eed9121')}
for key,(path,digest) in expected.items():assert sha(path)==getattr(a,'local_'+key+'_sha')==digest
assert sha(B/'AGENTS.md')=='68db8493e678a0cab6613610a8d87f4fca6597f8369ccd5a75cea089bfd41db6'
assert SID in (B/'claims'/T/'card.txt').read_text() and not (B/'claims'/T/'done.txt').exists()
assert len((D/'wave6-launches.jsonl').read_text().splitlines())==20
scope=json.loads((D/'active_cpu_wave.json').read_text());assert scope['wave']==6
summary=json.loads((D/'wave6-summary.json').read_text())
assert summary['completed_launches']==20 and summary['strict_successes']==2 and summary['task_active']
receipt_path=L/'wave6-final-git-receipt.json';note_path=L/'wave6-final-journal-receipt.txt'
assert not receipt_path.exists() and not note_path.exists()
for path in D.iterdir():
    if path.is_file() and path.suffix in {'.py','.sh'}:shutil.copy2(path,W/path.name)
assert sha(D/'sonic_grasp.py')==sha(W/'sonic_grasp.py')=='93a9f38949bb542c378b900de45e8209c85b703996ef09113973d02a4eeec13e'
assert sha(D/'branch_execution.py')=='14228ce96d7ab17872e6e2ee9d8876985727c2fc74fe370ea6d9099ab0369d32'
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '第六波20启动全部退出并报告/摘要/原始压缩包双端SHA核验。near真实ARDY多初值分支+SONIC输入闭环+独立手指预压1.5mm，两版各1例通过v5：HOLD最低125.795/127.078mm，全程机器人碰桌0N，右臂峰速1.348/1.345rad/s，身体限位超量0。静态分支/0.5mm滑落失败均保留。3.2.7 no-grip闭手前1119帧8类数组完全相同且未抬起；3.14新路线负对照、重复/新文本泛化/受控放置/整链实时性/用户纠正/实机仍待完成，目标ACTIVE。新安全动画同原运行时绘制，新增物理步0，仅本机页面；不称20次混合搜索为成功率。用户授权的唯一根入口/自有代码直接部署，未覆盖vendor/KIMODO/共享环境。'],
 cwd=B,env=env,capture_output=True,text=True,timeout=60)
note_path.write_text(note.stdout+note.stderr)
assert note.returncode==0,(note.returncode,note.stdout,note.stderr)
match=re.search(r'OK journal #(\d+)',note.stdout+note.stderr);assert match
now=datetime.datetime.now().astimezone().isoformat()
with (L/'steps.md').open('a') as f:
    f.write('\n## [WAVE6 FULL20 DUAL ARCHIVE / OWN GIT] '+now+'\n-Local report/bundle/summary independently verified: '+a.local_report_sha+' / '+a.local_bundle_sha+' / '+a.local_summary_sha+'.\n'+note.stdout+note.stderr)
git_env=env.copy()
for prefix in ['GIT_AUTHOR','GIT_COMMITTER']:
    git_env[prefix+'_NAME']='codex-hp-'+SID;git_env[prefix+'_EMAIL']=SID+'@worker00039.invalid'
def git(*items):return subprocess.check_output(['git','-c','gc.auto=0',*items],cwd=B,env=git_env,text=True)
before_head=git('rev-parse','HEAD').strip()
(W/'wave6-final-head.before').write_text(before_head+'\n')
(W/'wave6-final-staged.before').write_text(git('diff','--cached','--name-only'))
index=Path(git('rev-parse','--git-path','index').strip())
shutil.copy2(index if index.is_absolute() else B/index,W/'wave6-final-index.before')
before=git('ls-files','-s');(W/'wave6-final-blobs.before').write_text(before)
entry=B/f'ardy-grasp-run-{T}.sh'
own=[entry.name,str(report.relative_to(B)),f'claims/{T}/card.txt',f'claims/{T}/rules_seen',f'claims/{T}/rules_seen_after',f'logs/{T}/steps.md',str(note_path.relative_to(B))]
own += [str(path.relative_to(B)) for path in sorted(W.iterdir()) if path.is_file() and
    (path.suffix in {'.py','.sh','.json'} or path.name.endswith('-archive.sha256') or path.name.startswith('rules-read-') and path.suffix=='.md')]
for name in ['wave6-progress2-git-receipt.json','wave6-progress2-journal-receipt.txt']:
    path=L/name
    if path.exists():own.append(str(path.relative_to(B)))
assert len(set(own))==len(own)
git('add','-f','--',*own)
git('commit','--only','-m',f'ARDY wave6 full20: audited zero-table-contact free-base grasp in two runtimes; matched no-grip and failures retained; Track4 ACTIVE ({T})','--',*own)
after=git('ls-files','-s');(W/'wave6-final-blobs.after').write_text(after)
def others(data):return {row.split('\t',1)[1]:row.split('\t',1)[0] for row in data.splitlines() if row.split('\t',1)[1] not in own}
assert others(before)==others(after),'Other indexed blobs changed; do not reset'
commit=git('rev-parse','HEAD').strip()
changed=git('diff-tree','--no-commit-id','--name-only','-r',commit).splitlines()
assert all(path in own for path in changed)
assert git('log','-1','--format=%ae').strip()==SID+'@worker00039.invalid'
checks={}
for path in [entry,report,W/'sonic_grasp.py',W/'native_branch.py',W/'branch_execution.py',W/'run.sh',W/'wave6-summary.json']:
    relative=str(path.relative_to(B));saved=subprocess.check_output(['git','-c','gc.auto=0','show','HEAD:'+relative],cwd=B,env=git_env)
    digest=hashlib.sha256(saved).hexdigest();assert digest==sha(path)
    checks[relative]=dict(sha256=digest,tree=git('ls-tree','HEAD','--',relative).strip(),filesystem_mode=oct(path.stat().st_mode&0o777))
answer=dict(commit=commit,head_before=before_head,other_index_blobs_preserved=True,changed_paths=changed,
    verified_blobs=checks,local_report_sha256=a.local_report_sha,local_bundle_sha256=a.local_bundle_sha,
    local_summary_sha256=a.local_summary_sha,journal_number=int(match.group(1)),journal_receipt=note.stdout+note.stderr,
    no_push=True,task_active=True,remaining_wave6_launches=0,full_track4_complete=False,
    cutoff='Final Git receipt/postcommit steps tail occur after sealed20 archive; retained separately, not retroactively inside it')
receipt_path.write_text(json.dumps(answer,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('-Own full20 checkpoint='+commit+'; other indexed blobs preserved, key blobs/modes verified; no push. Receipt/tail separately retained after sealed archive.\n')
print(json.dumps(answer,indent=2))
