"""Install only this session's two implementations with drift checks/backups."""
import ast
import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path
from wave4_records import sha

B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert '745a0dbc-a26f-4c01-add8-7577fca612de' in (B/'claims'/T/'card.txt').read_text()
assert json.loads((D/'active_cpu_wave.json').read_text())['wave']==7
processes=subprocess.check_output(['ps','-eo','pid,args'],text=True).splitlines();assert len(processes)<20000
assert not any(str(D) in row and any(x in row for x in ['/sonic_grasp.py','/phase_generate_entry.py']) for row in processes)
versions={
 'sonic_grasp.py':('93a9f38949bb542c378b900de45e8209c85b703996ef09113973d02a4eeec13e','f01c16cc913983c9f2befd2abd49c9694f6de9f53fe59407ee42d4225136e219'),
 'adaptive_hand.py':('19d2094fc343a7010040f3b1400e50f8617a86797d5c4007d7bb4acfdd741f31','892bff4b931f9df1836d685b2cea0a233783f32cfdf8738e51cf41aeb038986f')}
for name,(old,new) in versions.items():
    candidate=D/(Path(name).stem+'.wave7.py');backup=W/(name+'.before-wave7-table')
    assert sha(D/name)==old and sha(candidate)==new and not backup.exists()
    ast.parse(candidate.read_text());assert candidate.stat().st_size<128*1024
for name in ['finger_clearance.py','cycle_latency.py']:ast.parse((D/name).read_text())
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '按用户最新授权，验证后的自有改进直接上传服务器且不改他人文件。本次仅替换自有D/sonic_grasp.py和adaptive_hand.py，先备份及旧SHA核验；新增finger_clearance与cycle_latency。桌面约束为显式可选0..5mm手指IK目标高度且保留原碰撞/扭矩/验收门；实际改进尚待物理复测。整循环wall观察无pacing、不改参考/力；default关闭桌面约束需保存轨迹回归。ARDY-off+所选源branch组合明确拒绝以防不完整消融冒充完全off。当前7/20测试退出，新seed43原文本抓持但LIFT手指碰桌、新文字静态筛选失败均保留；预算4CPU/AS16/300s/90s/累计3GiB不变。无GPU/实机/vendor/共享环境写。'],
 cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr;(L/'wave7-observer-deploy-receipt.txt').write_text(receipt)
assert note.returncode==0 and 'OK journal #' in receipt
installed={}
for name,(old,new) in versions.items():
    target=D/name;candidate=D/(Path(name).stem+'.wave7.py');backup=W/(name+'.before-wave7-table')
    assert sha(target)==old
    shutil.copy2(target,backup);assert sha(backup)==old
    mode=target.stat().st_mode&0o777;candidate.chmod(mode);os.replace(candidate,target)
    assert sha(target)==new and target.stat().st_mode&0o777==mode
    installed[name]=dict(old_sha256=old,new_sha256=new,backup=str(backup),mode=oct(mode))
record=dict(time=datetime.datetime.now().astimezone().isoformat(),physical_steps=0,installed=installed,
    journal_receipt=receipt,other_files_modified=False,new_features_physics_validated=False,
    direct_upload_authority='Human: 有任何对服务器里现有的内容改进的地方直接上传到服务器，不要改动别人的文件')
(W/'wave7-observer-deploy.json').write_text(json.dumps(record,indent=2)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave7_own_direct_deploy='+json.dumps(record,ensure_ascii=False)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE7 OWN TABLE-TARGET/LATENCY DEPLOY] '+json.dumps(record,ensure_ascii=False)+'\n')
print(json.dumps(record,indent=2))
