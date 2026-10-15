"""Correct input-text attribution without editing original evidence or ledgers."""
import datetime
import json
import os
import subprocess
from pathlib import Path
from wave4_records import sha

B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
old_result=D/'out/w6_branchpreload15_near327/result.json';generated=D/'out/generated_phases2/summary.json'
old=json.loads(old_result.read_text());summary=json.loads(generated.read_text())
reach=next(job for job in summary['jobs'] if job['stem']=='reach_s43')
assert old['source']['text']==reach['prompt']
scope_file=D/'active_cpu_wave.json';scope=json.loads(scope_file.read_text());assert scope['wave']==7
output=D/'out/w7-input-text-identity.json';assert not output.exists()
audit=dict(physical_steps=0,original_npz_sha256=old['source']['source_npz_sha256'],
    original_result_sha256=sha(old_result),generation_summary_sha256=sha(generated),
    original_text=old['source']['text'],reach43_text=reach['prompt'],texts_equal=True,
    reach43_seed_from_summary=reach['seed'],
    limitation='near_s42 vs reach_s43 is a different generated sample of the SAME text, not a text generalization test; filename seed is not enough attribution')
output.write_text(json.dumps(audit,indent=2)+'\n')
backup=W/'wave7-scope.before-input-amend.json';assert not backup.exists();backup.write_bytes(scope_file.read_bytes())
scope['plan']='Matched no-grip3.14 and fresh-process repeats in both runtimes; reach_s43 is same-text different sample, not text generalization. Generate genuinely different text with same seed under separate bounded CPU generation scope and source manifest, then physical execution. Also contact-qualified SETDOWN and whole-loop latency. Genuine human correction only if received.'
scope['input_identity_audit_sha256']=sha(output)
temporary=D/'active_cpu_wave.input-amend.json';assert not temporary.exists()
temporary.write_text(json.dumps(scope,indent=2)+'\n');os.replace(temporary,scope_file)
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave7_input_scope_amend='+json.dumps(scope,ensure_ascii=False)+'\n')
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 '更正journal#2320及第七波原计划文字：near_s42原结果source.text与generated_phases2/summary中reach_s43.prompt逐字相同；reach_s43仅不同样本/seed，不能称不同文本泛化。第七波仍<=20/4CPU/AS16/300s/90s/累计3GiB、旧波不动；新增真正不同文字的生成预算另登记，固定相同seed隔离文本变化。3.14 no-grip已退出且原场景/源/runtime同成功例，1119帧8类数组闭手前精确一致，闭手后手指最大差1.087975rad，OFF不抬起。327新进程重复已退出并严格成功，1491帧8类数组同原成功例精确一致；这是确定性复现而非随机成功率。当前2/20已退出，目标ACTIVE，无实机/GPU/共享vendor写。',
 '--field','voids=2320'],cwd=B,env=env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr;(L/'wave7-input-amend-receipt.txt').write_text(receipt)
assert note.returncode==0 and 'OK journal #' in receipt,(note.returncode,receipt)
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE7 INPUT TEXT ATTRIBUTION CORRECTION] '+datetime.datetime.now().astimezone().isoformat()+'\n'+receipt+'-same text proven from original result and generation summary; audit='+str(output)+' SHA='+sha(output)+'. No simulation step or old report rewrite.\n')
print(json.dumps(dict(audit=audit,receipt=receipt),indent=2))
