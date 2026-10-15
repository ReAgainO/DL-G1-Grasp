# 归档续接记录

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
backup: reports/open-issues.md.bak.20261009-075143
OK rebuilt /home/group4/group4_dasc7606c/reports/open-issues.md: 问题 280 / 事件 966 | OPEN=218 BLOCKED=10 WATCH=25 CLOSED=27

convention=include-newline
   数据行 966 | 问题 280 | JSON坏 0 | 空行 0 | 断链 0 | seq异常 0 | 缺字段 0 | state异常 0 | event异常 0 | 锚点缺失 0 | 锚点失配 0 | 锚点条数 0 | 锚点格式 0 | 视图问题数 0 | 视图事件数 0
-- exit=0 (0=链/JSON/seq/字段/state/锚点逐条/视图 全部完整)

## 四、失败项与原因

初检视图渲染964条，事实源966条；JSON坏0、断链0、seq异常0，失败项为视图事件数。
首次错误日志保留；没有重跑仿真、修改成功门或删除失败试验。

## 五、下一步建议

每次official issue_append后按官方流程重建issue_view，再verify；重复执行前先检查自身checkpoint，避免重复note/done。

## 六、复现方法

此脚本仅适用于本次确切失败checkpoint；满足所有前置断言才允许续接。
已提交或已关闭时不要重跑；若前置断言失败，应只读检查而不是删除回执。
