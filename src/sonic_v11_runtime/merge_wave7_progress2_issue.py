"""Append our evidence to the existing issue; never edit others' records/view."""
import json,os,re,subprocess
from pathlib import Path
from wave4_records import sha
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T;L=B/'logs'/T;W=B/'work'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
report=B/'reports'/f'{T}-wave7-progress2-report.md';summary=D/'wave7-progress2.json';assert report.is_file()
s=json.loads(summary.read_text());assert s['total_launches']==20 and not s['full_track4_complete']
issue='ISS-GRASP-ARDY-ATTRIBUTION-BLOCKED';events=[]
with (B/'claims/issues.jsonl').open() as f:
 for i,line in enumerate(f):
  assert i<10000;r=json.loads(line)
  if r['issue']==issue:events.append(r)
assert events and events[-1]['state']=='OPEN'
dest=W/'wave7-progress2-issue-evidence.json';receipt_path=L/'wave7-progress2-issue-receipt.txt';assert not dest.exists() and not receipt_path.exists()
env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(k,None)
body=(f'本TASKID更新自己的混合重定向线，不改其他方法历史或接管训练轴。真正不同文本same seed43的ARDY NPZ feaf256b..经七候选face匹配仍两版失败，持续face servo后MuJoCo3.2.7/3.14.0严格成功：HOLD最低111.100/113.424mm，腕相对滑移4.728/3.781mm，全程robot-table0N；无fixed-base/weld/外力/object-state/身体motor override，全29身体目标由official SONIC v1.1 encoder/decoder产生，手指独立。两版介入前670帧8数组精确一致；匹配no-grip闭手前1187/1172帧一致、闭手后真实分岔且不抬起；原near默认关闭1491帧8数组精确回归。仅此scene/config/文本族，非原生ARDY抓取/ARDY必要性/统计成功率/视觉/实机。SETDOWN原near两版掉落失败：落桌前腕相对滑移122.002/128.074mm、未RELEASE；20ms整周期仍失败、用户纠正0。本条保持OPEN。证据reports/{T}-wave7-progress2-report.md及/data/group4/{T}/wave7-progress2.json、原result/telemetry/raw contacts/源码快照；两个成功qpos回放已生成，回放积分0步。下一具体动作：bash /home/group4/group4_dasc7606c/ardy-grasp-run-{T}.sh status；本波20/20用尽，先journal登记新有界波再对SETDOWN连续双指→桌承重→RELEASE做500Hz审计与两版对照，禁止复用槽名或放宽安全门；需真人提供具体动作纠正才计数纠正试验。预计下一波<=20次CPU、4CPU/AS16/300s单次，空间重新预算。')
args=['bash',str(B/'work/20260930-0310-qoder-issuereg/issue_append.sh'),issue,'note','OPEN',
 '自有混合ARDY-SONIC新文本两版抓取通过；受控放置/实时/ARDY必要性仍未证',body,
 '--field','owner_task='+T,'--field','owner_scope=仅本TASKID混合重定向/独立手指，不接管他人训练轴',
 '--field','severity=高','--field','est_cost=下一有界CPU波，须先登记及重新预算',
 '--field','evidence='+str(report)+' SHA256='+sha(report)+'; '+str(summary)+' SHA256='+sha(summary)]
r=subprocess.run(args,cwd=B,env=env,capture_output=True,text=True,timeout=150);receipt=r.stdout+r.stderr
with receipt_path.open('x') as f:f.write(receipt)
assert r.returncode==0;match=re.search(r'seq=(\d+)',receipt);assert match
with (B/'claims/issues.jsonl').open() as f:own=[json.loads(line) for line in f if '"seq": '+match.group(1)+',' in line]
assert len(own)==1 and own[0]['issue']==issue and own[0]['owner_task']==T and own[0]['body']==body
view=subprocess.run(['bash',str(B/'work/20260930-0310-qoder-issuereg/issue_view.sh')],cwd=B,env=env,capture_output=True,text=True,timeout=150)
verify=subprocess.run(['bash',str(B/'work/20260930-0310-qoder-issuereg/issue_verify.sh')],cwd=B,env=env,capture_output=True,text=True,timeout=150)
answer=dict(previous_events=events,own_event=own[0],writer_receipt=receipt,view_exit=view.returncode,view_output=view.stdout+view.stderr,verify_exit=verify.returncode,verify_output=verify.stdout+verify.stderr,report_sha256=sha(report),summary_sha256=sha(summary),physical_steps=0,task_active=True)
with dest.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [OWN WAVE7 ISSUE EVIDENCE] '+json.dumps(answer,ensure_ascii=False)+'\n')
assert view.returncode==0 and verify.returncode==0
print(json.dumps({k:v for k,v in answer.items() if k!='previous_events'},indent=2))
