"""Continue this live task; register bounded static diagnostics before writes."""
import datetime,json,os,subprocess
from pathlib import Path
from wave4_records import sha
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;L=B/'logs'/T;W=B/'work'/T
rules='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert sha(B/'AGENTS.md')==rules
assert '745a0dbc-a26f-4c01-add8-7577fca612de' in (B/'claims'/T/'card.txt').read_text()
assert not (B/'claims'/T/'done.txt').exists()
latest=None
with (B/'claims/journal.log').open() as f:
 for line in f:
  r=json.loads(line)
  if r.get('task')==T:latest=r
assert latest is not None and latest['event'] not in ['done','blocked']
scope=json.loads((D/'active_cpu_wave.json').read_text());assert scope['wave']==7
launches=(D/'wave7-launches.jsonl').read_text().splitlines();assert len(launches)==10
ps=subprocess.check_output(['ps','-eo','pid,etimes,args'],text=True).splitlines()
assert len(ps)<20000 and not any(str(D) in row and any(n in row for n in ['/sonic_grasp.py','/phase_generate_entry.py','/generate_wave7_text.py']) for row in ps)
record_path=W/'wave7-part2-resume.json';assert not record_path.exists()
df=subprocess.check_output(['df','-B1','/home','/data/group4','/tmp'],text=True)
free=subprocess.check_output(['free','-h'],text=True)
actual=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0])
assert actual+64*1024**2<3*1024**3
assert os.statvfs(D).f_bavail*os.statvfs(D).f_frsize>30*1024**3+64*1024**2
probe=D/'wave7-part2-write-probe.bin'
with probe.open('xb') as f:f.write(b'\0'*(1024**2));f.flush();os.fsync(f.fileno())
assert probe.stat().st_size==1024**2
evidence=dict(time=datetime.datetime.now().astimezone().isoformat(),rules_sha256=rules,
 previous_task_event=latest,launches=10,remaining=10,task_bytes_before=actual,
 write_probe=dict(path=str(probe),bytes=probe.stat().st_size,sha256=sha(probe)),
 df=df,free=free,cpu_psi=Path('/proc/pressure/cpu').read_text(),memory_psi=Path('/proc/pressure/memory').read_text(),
 physical_steps=0,static_scan_bound='20 candidate evaluations, each arm4*15 IK iterations and hand35; one original7-branch replay for protocol parity; max2250 input frames,4CPU/AS16GiB/300s',
 authority='Human authorizes direct server improvements, own files/new unique files only; no changes to others/vendor/env/config, no GPU')
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '继续第七波余10槽。先零物理步诊断新文本静态筛选：原uniform7候选协议复现，另扫描最多20候选（实际源frame43及近邻/不同预压）；每候选arm4*15/hand35迭代硬界，4CPU/AS16GiB/300s，无GPU。现有生成源及失败保持不改，不放宽capture/hand/limits/table门。手指1mm桌面约束无实际指令变化与整链时延失败保留；本轮只写自有工具/流水/报告，按用户授权改进直接上传，不改他人文件。'],cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr
(L/'wave7-part2-resume-receipt.txt').write_text(receipt)
assert note.returncode==0 and 'OK journal #' in receipt
evidence['journal_receipt']=receipt
with record_path.open('x') as f:f.write(json.dumps(evidence,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE7 PART2 RESUME] '+json.dumps(evidence,ensure_ascii=False)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave7_part2_static_scope='+json.dumps(evidence,ensure_ascii=False)+'\n')
print(json.dumps(evidence,indent=2))
