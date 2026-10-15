"""Own-path Git checkpoint after independently verified ten-trial dual archive."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from wave4_records import sha

p=argparse.ArgumentParser()
for name in ['report','summary','bundle']:p.add_argument('--local-'+name+'-sha',required=True)
a=p.parse_args();B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
SID='745a0dbc-a26f-4c01-add8-7577fca612de';D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
expected={'report':(B/'reports'/f'{T}-wave7-progress1-report.md','e1dfcd8c2d2399ee49f18e9709466eec5b6dbc13e1df3028f81a3217b2091ca6'),
    'summary':(D/'wave7-progress1.json','f2f4c2b43ba07a79acd5f733d91ac161e75680210f089c2d4446437ecafdb4b9'),
    'bundle':(D/'wave7-progress1.tar.gz','e569b85ce382258df50ab78665035b21341e965e5cbc77269a0098006de54a9d')}
for name,(path,value) in expected.items():assert sha(path)==getattr(a,'local_'+name+'_sha')==value
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert SID in (B/'claims'/T/'card.txt').read_text() and not (B/'claims'/T/'done.txt').exists()
assert len((D/'wave7-launches.jsonl').read_text().splitlines())==10
assert sha(D/'sonic_grasp.py')=='f01c16cc913983c9f2befd2abd49c9694f6de9f53fe59407ee42d4225136e219'
receipt_path=L/'wave7-progress1-git-receipt.json';note_path=L/'wave7-progress1-journal-receipt.txt'
assert not receipt_path.exists() and not note_path.exists()
for path in D.iterdir():
    if path.is_file() and path.suffix in {'.py','.sh'}:shutil.copy2(path,W/path.name)
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
    '第七波前10启动全部退出并报告/摘要/原始包111419044B双端SHA一致，余10槽目标ACTIVE。原near两版新进程重复严格成功；3.14匹配no-grip真实分岔且不抬起。纠正旧reach43同文本归因；新seed43真正不同文本已改变SONIC输入/输出但两版静态可达性拒绝，同文字seed43抓持但LIFT指垫碰桌。自有代码直接部署：整循环计时/可选手指目标桌面约束，默认原成功1491帧8数组精确回归。1mm约束两版没有改变手指/扭矩/物理轨迹，仍碰桌，不称改进成功。3.2.7完整周期p95=54.462ms且2981/2981超20ms，冷生成81.115s，非实时；用户纠正/SETDOWN/全身COM/COP/实机仍未完成。未修改他人文件/vendor/共享环境、无GPU。十次混合验证不算成功率。'],
    cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr;note_path.write_text(receipt);assert note.returncode==0
match=re.search(r'OK journal #(\d+)',receipt);assert match
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE7 FIRST10 DUAL ARCHIVE/OWN GIT]\n-Verified local report/summary/bundle SHA='+a.local_report_sha+' / '+a.local_summary_sha+' / '+a.local_bundle_sha+'\n'+receipt)
git_env=env.copy()
for prefix in ['GIT_AUTHOR','GIT_COMMITTER']:
    git_env[prefix+'_NAME']='codex-hp-'+SID;git_env[prefix+'_EMAIL']=SID+'@worker00039.invalid'
def git(*items):return subprocess.check_output(['git','-c','gc.auto=0',*items],cwd=B,env=git_env,text=True)
head=git('rev-parse','HEAD').strip();(W/'wave7-progress1-head.before').write_text(head+'\n')
(W/'wave7-progress1-staged.before').write_text(git('diff','--cached','--name-only'))
index=Path(git('rev-parse','--git-path','index').strip());shutil.copy2(index if index.is_absolute() else B/index,W/'wave7-progress1-index.before')
before=git('ls-files','-s');(W/'wave7-progress1-blobs.before').write_text(before)
entry=B/f'ardy-grasp-run-{T}.sh';report=expected['report'][0]
own=[entry.name,str(report.relative_to(B)),f'claims/{T}/card.txt',f'claims/{T}/rules_seen_after',f'logs/{T}/steps.md',str(note_path.relative_to(B))]
own += [str(path.relative_to(B)) for path in sorted(W.iterdir()) if path.is_file() and
    (path.suffix in {'.py','.sh','.json'} or path.name.endswith('-archive.sha256') or path.name.startswith('rules-read-') and path.suffix=='.md')]
own += [str(path.relative_to(B)) for path in sorted(L.glob('wave7-*.txt')) if path!=note_path]
assert len(own)==len(set(own))
git('add','-f','--',*own)
git('commit','--only','-m',f'ARDY wave7 first10: honest text-failure/ineffective clearance controls and whole-cycle latency; owned direct deployment; Track4 ACTIVE ({T})','--',*own)
after=git('ls-files','-s');(W/'wave7-progress1-blobs.after').write_text(after)
def others(data):return {row.split('\t',1)[1]:row.split('\t',1)[0] for row in data.splitlines() if row.split('\t',1)[1] not in own}
assert others(before)==others(after),'Other staged blobs drifted; do not reset'
commit=git('rev-parse','HEAD').strip();changed=git('diff-tree','--no-commit-id','--name-only','-r',commit).splitlines()
assert all(path in own for path in changed) and git('log','-1','--format=%ae').strip()==SID+'@worker00039.invalid'
checks={}
for path in [entry,report,W/'sonic_grasp.py',W/'adaptive_hand.py',W/'finger_clearance.py',W/'cycle_latency.py',W/'run.sh',W/'wave7-progress1.json']:
    relative=str(path.relative_to(B));saved=subprocess.check_output(['git','-c','gc.auto=0','show','HEAD:'+relative],cwd=B,env=git_env)
    value=hashlib.sha256(saved).hexdigest();assert value==sha(path)
    checks[relative]=dict(sha256=value,tree=git('ls-tree','HEAD','--',relative).strip(),mode=oct(path.stat().st_mode&0o777))
answer=dict(commit=commit,head_before=head,other_index_blobs_preserved=True,changed_paths=changed,verified_blobs=checks,
    journal_number=int(match.group(1)),journal_receipt=receipt,no_push=True,task_active=True,remaining_wave7_slots=10,
    full_track4_complete=False,dual_archive_sha256={name:value for name,(path,value) in expected.items()},
    cutoff='Git receipt and final log tail occur after immutable first10 archive, retained separately; no historical archive rewritten')
receipt_path.write_text(json.dumps(answer,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('-Own checkpoint commit='+commit+'; other staged blobs preserved; no push. Receipt/log tail separate from immutable bundle.\n')
print(json.dumps(answer,indent=2))
