"""Register final three bounded controls only after both positive rollouts exit."""
import datetime,json,os,subprocess
from pathlib import Path
from wave4_records import sha
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T;L=B/'logs'/T;W=B/'work'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert '745a0dbc-a26f-4c01-add8-7577fca612de' in (B/'claims'/T/'card.txt').read_text()
assert len((D/'wave7-launches.jsonl').read_text().splitlines())==17
ps=subprocess.check_output(['ps','-eo','args'],text=True).splitlines();assert len(ps)<20000
assert not any(str(D/'sonic_grasp.py') in row for row in ps)
assert sha(D/'sonic_grasp.py')=='28512909961057ab7f9c93144f633b5f0ca7f6b5aae9c1b05d80661baa59165c'
positives={}
for ver in ['327','314']:
 p=D/'out'/('w7_faceservo_newtext'+ver)/'result.json';r=json.loads(p.read_text())
 assert r['success'] and all(r['gates'].values()) and r['face_aligned_servo']['calls']>0
 assert not r['base_fixture'] and not r['body_action_override'] and r['peak_external_force']==0
 positives[ver]=dict(result_sha256=sha(p),version=r['runtime_stamp']['mujoco_version'],hold_min_mm=r['hold_min_lift_m']*1000,slip_mm=r['hold_slip_m']*1000,table_peak_N=r['balance_audit_summary']['robot_table_all_max_normal_N'])
actual=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0]);assert actual+256*1024**2<3*1024**3
assert os.statvfs(D).f_bavail*os.statvfs(D).f_frsize>30*1024**3+256*1024**2
env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(k,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '新文本face持续servo两MuJoCo严格通过，保持原安全门/全29身体官方SONIC/独立手指、无fixture外力；不是实时/原生ARDY/ARDY必要性/统计成功率。当前17/20退出，最后三槽用于各版本同代码同源no-grip对照和3.2.7原near默认关闭完整回归。每次4CPU/AS16/300s/90s/45000step/累计3GiB。只读前缀对照最多2250帧8数组，朝向审计每phase32总160状态；并保存raw接触。SETDOWN两版失败、用户纠正0保持；他人文件/env/vendor不动。'],cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr
with (L/'wave7-face-controls-receipt.txt').open('x') as f:f.write(receipt)
assert note.returncode==0 and 'OK journal #' in receipt
answer=dict(time=datetime.datetime.now().astimezone().isoformat(),positives=positives,journal_receipt=receipt,remaining_slots=3,task_active=True,physical_steps=0,task_bytes_before=actual)
with (W/'wave7-face-controls-scope.json').open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [FACE SERVO CONTROLS SCOPE] '+json.dumps(answer,ensure_ascii=False)+'\n')
print(json.dumps(answer,indent=2))
