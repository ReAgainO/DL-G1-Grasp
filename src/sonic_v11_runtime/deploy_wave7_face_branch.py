"""Atomic own-file deployment with source drift, identity and idle guards."""
import ast,datetime,json,os,shutil,subprocess
from pathlib import Path
from wave4_records import sha
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert '745a0dbc-a26f-4c01-add8-7577fca612de' in (B/'claims'/T/'card.txt').read_text()
assert len((D/'wave7-launches.jsonl').read_text().splitlines())==12
ps=subprocess.check_output(['ps','-eo','pid,args'],text=True).splitlines();assert len(ps)<20000
assert not any(str(D) in row and any(n in row for n in ['/sonic_grasp.py','/phase_generate_entry.py']) for row in ps)
assert sha(D/'branch_face_ik.py')=='1492f257abb7dd1c3a5ff61b87605ec46e2ae0d46b84ff38651495f11bdc84e4'
versions={
 'sonic_grasp.py':('f01c16cc913983c9f2befd2abd49c9694f6de9f53fe59407ee42d4225136e219','e4450a7f13374938a5a81003666440aee6b1f1537a47112217cd42dd349de1b8'),
 'native_branch.py':('3200af709404873baf07ff36042b13b8131555c5290af7bd9a410103126eac28','1f956007892cca5a9d170809052ccd864244e7370fd07046082fa131f3c7f73d')}
for name,(old,new) in versions.items():
 candidate=D/(Path(name).stem+'.facebranch.py');backup=W/(name+'.before-facebranch')
 assert sha(D/name)==old and sha(candidate)==new and not backup.exists();ast.parse(candidate.read_text())
 assert candidate.stat().st_size<128*1024
record_path=W/'wave7-facebranch-deploy.json';assert not record_path.exists()
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '只部署本会话自有sonic_grasp/native_branch可选face朝向分支及live筛选失败状态审计；双SHA/旧件备份/权限/无live job闸。--branch-face-alignment默认关闭，开启时source七候选上界、4*15arm/35hand上界不变，align物体face yaw和20.05mrad优化clip；hand预压/face区域匹配实际独立手指设定，原静态/动力验收门不放宽。仅虚拟SONIC输入，不改ARDY权重/SONIC/vendor/身体motor/actuald/物体/碰撞mask。当前12/20，下一先原成功默认关闭回归，再新文字两版live动力学各1次；4CPU/AS16/300s/90s/45000步/累计3GiB。静态两版通过不称抓取成功，SETDOWN两版失败保留。'],cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr;(L/'wave7-facebranch-deploy-receipt.txt').write_text(receipt)
assert note.returncode==0 and 'OK journal #' in receipt
installed={}
for name,(old,new) in versions.items():
 target=D/name;candidate=D/(Path(name).stem+'.facebranch.py');backup=W/(name+'.before-facebranch')
 assert sha(target)==old;shutil.copy2(target,backup);assert sha(backup)==old
 mode=target.stat().st_mode&0o777;candidate.chmod(mode);os.replace(candidate,target)
 assert sha(target)==new and target.stat().st_mode&0o777==mode
 installed[name]=dict(old_sha256=old,new_sha256=new,backup=str(backup),mode=oct(mode))
record=dict(time=datetime.datetime.now().astimezone().isoformat(),installed=installed,
 journal_receipt=receipt,physical_steps=0,other_files_modified=False,physics_validation_pending=True)
with record_path.open('x') as f:f.write(json.dumps(record,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [OWN FACE BRANCH DEPLOY] '+json.dumps(record,ensure_ascii=False)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave7_facebranch_deploy='+json.dumps(record,ensure_ascii=False)+'\n')
print(json.dumps(record,indent=2))
