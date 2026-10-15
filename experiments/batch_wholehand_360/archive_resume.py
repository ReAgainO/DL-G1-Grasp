"""Resume exactly the failed issue-view checkpoint; no duplicate notes/close."""
from pathlib import Path
import importlib.util,json,hashlib,shutil,datetime,resource
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
T='20261009-021611-codex-415484ce'
R=Path('/data/group4')/T;B=Path('/home/group4/group4_dasc7606c');W=B/'work'/T
assert Path(__file__).resolve().parent==R
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected=json.loads((W/'archive-expectations.json').read_text())
assert sha(R/'archive_batch.py')==expected['data'][str(R/'archive_batch.py')],'original archive build changed'
assert (R/'logs/archive-issue-verify.log').exists(),'expected retained first failure missing'
for name in ['archive-precheck.json','own-ledger-preclose.json','own-ledger-postclose.json','close-receipt.json']:
    assert not (W/name).exists(),('unexpected later checkpoint; inspect instead of repeat',name)
assert not (R/'archive-receipt.json').exists() and not (R/'git-initial.json').exists()
assert not (B/'claims'/T/'done.txt').exists(),'already closed; do not repeat'
spec=importlib.util.spec_from_file_location('original_own_archive',R/'archive_batch.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
original_command=module.command
def recorded_command(args,label,timeout=120):
    return original_command(args,label+'-resume-01',timeout)
module.command=recorded_command
def existing_rules_after():
    actual=sha(B/'AGENTS.md')
    claim=B/'claims'/T
    assert actual==(claim/'rules_seen').read_text().split()[0]==(claim/'rules_seen_after').read_text().split()[0]
    module.append_steps('Resume uses already written rules_seen_after, unchanged verified SHA '+actual+'; no overwrite.')
    return actual
module.own_rules_after=existing_rules_after
def retained_issue_note(issue_id,title,body,label):
    history=[json.loads(line) for line in (B/'claims/issues.jsonl').read_text().splitlines()]
    matches=[row for row in history if row.get('issue')==issue_id and row.get('event')=='note' and
             row.get('reporter_task')==T and row.get('title')==title and row.get('body')==body]
    assert len(matches)==1,('must find exactly one already appended matching own note; no automatic retry append',issue_id,len(matches))
    module.append_steps('Retained existing issue note '+issue_id+' seq='+str(matches[0]['seq'])+'; not appended again, current shared state left untouched.')
module.issue_note=retained_issue_note
module.append_steps('Archive first attempt failed only at issue_verify: view964 events versus fact966, chain/JSON/seq/fields valid; original archive-issue-verify.log retained SHA '+sha(R/'logs/archive-issue-verify.log')+'; bounded resume source SHA '+sha(__file__))
view=module.command(['bash',str(module.ISSUES/'issue_view.sh')],'issue-view')
verified=module.command(['bash',str(module.ISSUES/'issue_verify.sh')],'issue-verify-precheck')
note='''# 归档续接记录

## 一、结论

正式360轮及视频核验结果不变；本笔记仅记录归档流程。
首次归档停止于问题清单视图缺少刚追加的两条事件；事实日志无断链或JSON错误。
已用官方工具重建视图并通过复核，不重复追加问题事件，不覆写首次错误。

## 二、操作步骤

1. 验证原archive_batch.py仍与已接收证据包SHA相同，并确认未产生Git初次提交、archive-precheck或done。
2. 重用并核对已写rules_seen_after，不重新写入。
3. 调用官方issue_view.sh重建派生视图（工具自动备份旧视图），再调用issue_verify.sh。
4. 原prepare函数后续执行时，只核对恰好一条已存在的本任务匹配note，不再追加；所有后续核心核验仍执行。
5. 本任务提交、官方关闭及最终状态以archive/close/Git/own-ledger回执为准；本笔记不代替关闭回执。

## 三、实测证据

首次错误日志：logs/archive-issue-verify.log。
重建与复核日志：logs/archive-issue-view-resume-01.log、logs/archive-issue-verify-precheck-resume-01.log。
'''+view+'\n'+verified+'''
## 四、失败项与原因

初检视图渲染964条，事实源966条；JSON坏0、断链0、seq异常0，失败项为视图事件数。
首次错误日志保留；没有重跑仿真、修改成功门或删除失败试验。

## 五、下一步建议

每次official issue_append后按官方流程重建issue_view，再verify；重复执行前先检查自身checkpoint，避免重复note/done。

## 六、复现方法

此脚本仅适用于本次确切失败checkpoint；满足所有前置断言才允许续接。
已提交或已关闭时不要重跑；若前置断言失败，应只读检查而不是删除回执。
'''
with (R/'ARCHIVE-NOTES.md').open('x') as f:f.write(note)
shutil.copy2(R/'ARCHIVE-NOTES.md',W/'ARCHIVE-NOTES.md')
assert sha(R/'ARCHIVE-NOTES.md')==sha(W/'ARCHIVE-NOTES.md')
module.prepare()
