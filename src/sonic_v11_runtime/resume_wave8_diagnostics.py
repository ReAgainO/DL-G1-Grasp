"""Resume this owned task with bounded, zero-integration SETDOWN diagnostics."""
import datetime
import json
import os
import subprocess
from pathlib import Path
from wave4_records import sha

B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
SID='745a0dbc-a26f-4c01-add8-7577fca612de'
RULES='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert sha(B/'AGENTS.md')==RULES
assert SID in (B/'claims'/T/'card.txt').read_text()
assert not (B/'claims'/T/'done.txt').exists()
latest=None
with (B/'claims/journal.log').open() as f:
    for line in f:
        r=json.loads(line)
        if r.get('task')==T:latest=r
assert latest and latest['event'] not in ['done','blocked']
assert json.loads((D/'active_cpu_wave.json').read_text())['wave']==7
launches=[json.loads(x) for x in (D/'wave7-launches.jsonl').read_text().splitlines()]
assert len(launches)==20
assert all((D/'out'/x['name']/'result.json').exists() for x in launches)
ps=subprocess.check_output(['ps','-eo','pid,args'],text=True).splitlines()
assert len(ps)<20000
assert not any(str(D) in row and any(x in row for x in ['/sonic_grasp.py','/generate_wave7_text.py','/render_verified_replay.py']) for row in ps)
used=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0])
assert used+50*1024**2<3*1024**3
assert os.statvfs(D).f_bavail*os.statvfs(D).f_frsize>30*1024**3
dest=W/'wave8-diagnostic-resume.json';assert not dest.exists()
probe=D/'wave8-write-probe.bin'
with probe.open('xb') as f:
    f.write(b'\0'*1024**2);f.flush();os.fsync(f.fileno())
assert probe.stat().st_size==1024**2
record=dict(time=datetime.datetime.now().astimezone().isoformat(),rules_sha256=RULES,
    previous_turn_classification='progress: own deployed face servo, two-runtime new-text positive/negative/default tests, dual-SHA raw archive and own Git; verified live server hashes match',
    previous_task_event=latest,wave7_launches=20,wave7_remaining=0,physical_steps=0,
    task_bytes_before=used,write_probe=dict(path=str(probe),bytes=probe.stat().st_size,sha256=sha(probe)),
    diagnostic_bounds='2 runtimes sequentially; each <=45000 telemetry rows, <=2250 trajectory frames, <=200 FK states; no mj_step; 4CPU/AS16GiB/300s; output<=2MiB',
    plan='Measure HOLD->SETDOWN actual wrist/reference/decoded-target mismatch, 500Hz opposed-force gaps and slip before first table support; do not assume actual-state reanchoring fixes it',
    physics_registration='No new physical launch authorized by this record; wave7 exhausted, new bounded wave required',
    df=subprocess.check_output(['df','-B1','/home','/data/group4','/tmp'],text=True),
    free=subprocess.check_output(['free','-h'],text=True),
    cpu_psi=Path('/proc/pressure/cpu').read_text(),memory_psi=Path('/proc/pressure/memory').read_text(),
    authority='Only own/new uniquely owned files; no teammates/vendor/weights/shared environment/config/GPU/real robot/public service changes')
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
reply=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '上轮实际进展：自有持续face servo直接部署，两版真正新文本严格抓取和匹配no-grip/default回归，双端SHA封存及独立Git25fcc13。当前主代码285129和规则9e2c未漂移，20/20启动已退出，无自有重活残留。继续先零物理步诊断SETDOWN：每版<=45000遥测/2250轨迹/200FK，4CPU/AS16/300s；500Hz夹持/滑移与25Hz实际/reference/decoder分开，不先认定root cause。本记录不重置第七波/不增加物理槽；累计3GiB不增，不删旧证据，不改他人文件。AGENTS聚合读取截断后逐段补读180-340/340-500/500-640及595-640长节；本机缺test_cpu_trial_guard和远端误查cpu-trials.json分别已定位，正确wave7-launches20行存在，不当成服务器缺档。'],
 cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=reply.stdout+reply.stderr
(L/'wave8-diagnostic-resume-receipt.txt').write_text(receipt)
assert reply.returncode==0 and 'OK journal #' in receipt,(reply.returncode,receipt)
record['journal_receipt']=receipt
with dest.open('x') as f:f.write(json.dumps(record,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE8 DIAGNOSTIC RESUME] '+json.dumps(record,ensure_ascii=False)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave8_diagnostic_scope='+json.dumps(record,ensure_ascii=False)+'\n')
print(json.dumps(record,indent=2))
