"""Deploy only this session's optional servo and audit-label fix, while idle."""
import ast,datetime,json,os,shutil,subprocess
from pathlib import Path
from wave4_records import sha
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert '745a0dbc-a26f-4c01-add8-7577fca612de' in (B/'claims'/T/'card.txt').read_text()
assert len((D/'wave7-launches.jsonl').read_text().splitlines())==15
ps=subprocess.check_output(['ps','-eo','pid,args'],text=True).splitlines();assert len(ps)<20000
assert not any(str(D) in row and any(n in row for n in ['/sonic_grasp.py','/phase_generate_entry.py']) for row in ps)
versions={
 'sonic_grasp.py':('e4450a7f13374938a5a81003666440aee6b1f1537a47112217cd42dd349de1b8','28512909961057ab7f9c93144f633b5f0ca7f6b5aae9c1b05d80661baa59165c','sonic_grasp.faceservo.py'),
 'branch_face_ik.py':('1492f257abb7dd1c3a5ff61b87605ec46e2ae0d46b84ff38651495f11bdc84e4','c9e1843d2a86387b5984a1a6800542beef37f8acb994196bc88893938848aad9','branch_face_ik.faceservo.py'),
 'audit_setdown.py':('b694796f4d864b1210bf04f15283f2190ea39ebd6d9262a3fbc97aca41d39d68','90c022cc7acf9b2d950b64646d17820c167dab35c05f5d934fc675a99e1a27d3','audit_setdown.fixed.py')}
record_path=W/'wave7-faceservo-deploy.json';assert not record_path.exists()
for name,(old,new,stage) in versions.items():
 assert sha(D/name)==old and sha(D/stage)==new and not (W/(name+'.before-faceservo')).exists()
 assert (D/stage).stat().st_size<128*1024;ast.parse((D/stage).read_text())
actual=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0]);assert actual+160*1024**2<3*1024**3
assert shutil.disk_usage(D).free>30*1024**3+160*1024**2
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '仅原子部署自有sonic_grasp/branch_face_ik可选face-aligned-servo，默认关闭；PREGRASP/DESCEND/ALIGN/CLOSE的5Hz参考IK保持所选物体face轴（每次15迭代，最多450次），原0.06rad/C2/速度/限位/碰桌门不变，身体仍全29 official SONIC，无actuald/motor/object/force override。两版上一静态face分支均strict失败，25Hz诊断朝向在后续阶段漂移30-45度，仅提示非因果证据。15/20退出余5。后续两版同新文本只加servo标志测试，逐数组前缀回归；保持4CPU/AS16/300s/45000step/累计3GiB。audit_setdown旧无RELEASE时before_release字段实为停止前，#2345已更正，新版置null另存at_stop；旧产物不覆盖。'],cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr
with (L/'wave7-faceservo-deploy-receipt.txt').open('x') as f:f.write(receipt)
assert note.returncode==0 and 'OK journal #' in receipt
installed={}
for name,(old,new,stage) in versions.items():
 target=D/name;candidate=D/stage;backup=W/(name+'.before-faceservo');assert sha(target)==old
 shutil.copy2(target,backup);assert sha(backup)==old
 mode=target.stat().st_mode&0o777;candidate.chmod(mode);os.replace(candidate,target)
 assert sha(target)==new and target.stat().st_mode&0o777==mode
 installed[name]=dict(old_sha256=old,new_sha256=new,backup=str(backup),mode=oct(mode))
record=dict(time=datetime.datetime.now().astimezone().isoformat(),installed=installed,journal_receipt=receipt,
 task_bytes_before=actual,physical_steps=0,other_files_modified=False,physics_validation_pending=True)
with record_path.open('x') as f:f.write(json.dumps(record,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [OWN FACE SERVO DEPLOY] '+json.dumps(record,ensure_ascii=False)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave7_faceservo_deploy='+json.dumps(record,ensure_ascii=False)+'\n')
print(json.dumps(record,indent=2))
