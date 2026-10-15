"""Bounded evidence-only replay preparation, without new physics or GPU."""
import datetime,json,os,shutil,subprocess
from pathlib import Path
from wave4_records import sha
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T;L=B/'logs'/T;W=B/'work'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert len((D/'wave7-launches.jsonl').read_text().splitlines())==20
ps=subprocess.check_output(['ps','-eo','args'],text=True).splitlines();assert len(ps)<20000
assert not any(str(D/'sonic_grasp.py') in row for row in ps)
for ver in ['327','314']:
 r=json.loads((D/'out'/('w7_faceservo_newtext'+ver)/'result.json').read_text());assert r['success'] and all(r['gates'].values())
 c=json.loads((D/'out'/f'w7-faceservo-nogrip{ver}.json').read_text());assert c['on_success'] and not c['off_success'] and all(c['preclose_arrays_exact'].values())
reg=json.loads((D/'out/w7-faceservo-default-regression327.json').read_text());assert all(v['exact'] for v in reg['arrays'].values())
for name,digest in {'render_verified_replay.py':'037fb3a8211b760899e30ea0d7da264d1318c6df7fd2e75f5b932c70186a8d0b','audit_release_destination.py':'a37f00591d7ec4679ae6e3110fc5f70d0dc8ea22017cdfbe7d24cb14108fce77'}.items():assert sha(D/name)==digest
for name in ['w7_faceservo_replay327','w7_faceservo_replay314']:assert not (D/'out'/name).exists()
actual=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0]);assert actual+128*1024**2<3*1024**3
assert shutil.disk_usage(D).free>30*1024**3+128*1024**2
env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(k,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '第七波20/20退出，最新默认关闭1491帧8数组精确回归；两版新文本matched no-grip不抬起且闭手前1187/1172帧精确一致。追加零物理步保存姿态朝向160状态/版与落点审计<=45000telemetry/5760000 raw rows/版，输出append不改原result。将两版成功实际qpos用现有OSMesa纯CPU renderer各最多375帧640x240/12.5fps流式ffmpeg单线程渲染，4CPU/AS16/300s/累计3GiB，不用GPU不重算physics；保留runtime/模型/轨迹/视频sha和非实时/独立手指/非原生ARDY标签。预算128MiB，后续增量包还须单独核未压缩上界。'],cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr
with (L/'wave7-replay-scope-receipt.txt').open('x') as f:f.write(receipt)
assert note.returncode==0 and 'OK journal #' in receipt
answer=dict(time=datetime.datetime.now().astimezone().isoformat(),task_bytes_before=actual,physical_steps=0,journal_receipt=receipt,task_active=True,render_frames_bound_per_version=375)
with (W/'wave7-replay-scope.json').open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE7 REPLAY SCOPE] '+json.dumps(answer,ensure_ascii=False)+'\n')
print(json.dumps(answer,indent=2))
