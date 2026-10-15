"""Explicit own-path Git checkpoint, preserving all other indexed blobs."""
import argparse,hashlib,json,os,re,shutil,subprocess
from pathlib import Path
from wave4_records import sha
p=argparse.ArgumentParser()
for name in ['report','summary','bundle']:p.add_argument('--local-'+name+'-sha',required=True)
a=p.parse_args();B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
SID='745a0dbc-a26f-4c01-add8-7577fca612de';D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
expected={'report':B/'reports'/f'{T}-wave7-progress2-report.md','summary':D/'wave7-progress2.json','bundle':D/'wave7-progress2.tar.gz'}
for name,path in expected.items():
 value=getattr(a,'local_'+name+'_sha');assert re.fullmatch('[0-9a-f]{64}',value) and sha(path)==value
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert SID in (B/'claims'/T/'card.txt').read_text() and not (B/'claims'/T/'done.txt').exists()
summary=json.loads(expected['summary'].read_text());assert summary['total_launches']==20 and summary['remaining_slots']==0
assert len((D/'wave7-launches.jsonl').read_text().splitlines())==20
assert sha(D/'sonic_grasp.py')=='28512909961057ab7f9c93144f633b5f0ca7f6b5aae9c1b05d80661baa59165c'
receipt_path=L/'wave7-progress2-git-receipt.json';note_path=L/'wave7-progress2-journal-receipt.txt'
assert not receipt_path.exists() and not note_path.exists()
for path in D.iterdir():
 if path.is_file() and path.suffix in {'.py','.sh'}:shutil.copy2(path,W/path.name)
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '第七波20次全退出并报告/摘要/增量原始包双端SHA相同。真正不同文本face静态匹配后两版仍失败；追加持续face朝向servo后3.2.7/3.14严格通过，HOLD最低111.100/113.424mm，滑移4.728/3.781mm，全程桌接触0N，无fixture/外力/身体motor override；介入前两版670帧8数组精确一致。各版匹配no-grip实际指令分岔且不抬起；原near默认关闭完整回归精确不变。有限样本不称原生ARDY/ARDY必要性/统计成功率/实时。SETDOWN两版实际掉落/超时保留、用户纠正0/视觉/COMCOP/实机未完成，目标ACTIVE；此波余0，后续必须新登记有界波，不复用槽名/绕过计数。只改自己文件，未改他人/vendor/env，无GPU。'],cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr
with note_path.open('x') as f:f.write(receipt)
assert note.returncode==0;match=re.search(r'OK journal #(\d+)',receipt);assert match
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE7 PROGRESS2 DUAL ARCHIVE/OWN GIT]\n-Local report/summary/bundle='+a.local_report_sha+' / '+a.local_summary_sha+' / '+a.local_bundle_sha+'\n'+receipt)
git_env=env.copy()
for prefix in ['GIT_AUTHOR','GIT_COMMITTER']:
 git_env[prefix+'_NAME']='codex-hp-'+SID;git_env[prefix+'_EMAIL']=SID+'@worker00039.invalid'
def git(*items):return subprocess.check_output(['git','-c','gc.auto=0',*items],cwd=B,env=git_env,text=True)
head=git('rev-parse','HEAD').strip()
with (W/'wave7-progress2-head.before').open('x') as f:f.write(head+'\n')
with (W/'wave7-progress2-staged.before').open('x') as f:f.write(git('diff','--cached','--name-only'))
index=Path(git('rev-parse','--git-path','index').strip());backup=W/'wave7-progress2-index.before';assert not backup.exists()
shutil.copy2(index if index.is_absolute() else B/index,backup)
before=git('ls-files','-s')
with (W/'wave7-progress2-blobs.before').open('x') as f:f.write(before)
entry=B/f'ardy-grasp-run-{T}.sh';report=expected['report']
own=[entry.name,str(report.relative_to(B)),f'claims/{T}/card.txt',f'claims/{T}/rules_seen_after',f'logs/{T}/steps.md',str(note_path.relative_to(B))]
own += [str(path.relative_to(B)) for path in sorted(W.iterdir()) if path.is_file() and (path.suffix in {'.py','.sh','.json'} or path.name.endswith('-archive.sha256') or path.name.startswith('rules-read-') and path.suffix=='.md')]
own += [str(path.relative_to(B)) for path in sorted(L.glob('wave7-*.txt')) if path!=note_path]
assert len(own)==len(set(own))
git('add','-f','--',*own)
git('commit','--only','-m',f'ARDY wave7: verified new-text face-servo lift and paired no-grip; retain setdown failures; owned-only deployment; Track4 ACTIVE ({T})','--',*own)
after=git('ls-files','-s')
with (W/'wave7-progress2-blobs.after').open('x') as f:f.write(after)
def others(data):return {row.split('\t',1)[1]:row.split('\t',1)[0] for row in data.splitlines() if row.split('\t',1)[1] not in own}
assert others(before)==others(after),'Other staged blobs drifted: do not reset'
commit=git('rev-parse','HEAD').strip();changed=git('diff-tree','--no-commit-id','--name-only','-r',commit).splitlines()
assert all(path in own for path in changed) and git('log','-1','--format=%ae').strip()==SID+'@worker00039.invalid'
checks={}
for path in [entry,report,W/'sonic_grasp.py',W/'native_branch.py',W/'branch_face_ik.py',W/'audit_setdown.py',W/'run.sh',W/'wave7-progress2.json']:
 relative=str(path.relative_to(B));saved=subprocess.check_output(['git','-c','gc.auto=0','show','HEAD:'+relative],cwd=B,env=git_env)
 value=hashlib.sha256(saved).hexdigest();assert value==sha(path)
 checks[relative]=dict(sha256=value,tree=git('ls-tree','HEAD','--',relative).strip(),mode=oct(path.stat().st_mode&0o777))
answer=dict(commit=commit,head_before=head,other_index_blobs_preserved=True,changed_paths=changed,verified_blobs=checks,
 journal_number=int(match.group(1)),journal_receipt=receipt,no_push=True,task_active=True,remaining_wave7_slots=0,
 full_track4_complete=False,dual_archive_sha256={name:getattr(a,'local_'+name+'_sha') for name in expected},
 cutoff='Git receipt and final log tail postdate immutable incremental archive; retained separately, no historical archive rewritten')
with receipt_path.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('-Own commit='+commit+'; other indexed blobs preserved; no push; final tail/receipt separate.\n')
print(json.dumps(answer,indent=2))
