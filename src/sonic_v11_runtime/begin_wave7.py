"""Renew bounded20 only after sealed20; no physics, no shared vendor writes."""
import argparse
import datetime
import json
import os
import re
import resource
import shutil
import subprocess
from pathlib import Path
from wave4_records import sha

resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
p=argparse.ArgumentParser();p.add_argument('--wrapper-sha',required=True);p.add_argument('--entry-sha',required=True);a=p.parse_args()
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
SID='745a0dbc-a26f-4c01-add8-7577fca612de'
rules='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert sha(B/'AGENTS.md')==rules
assert SID in (B/'claims'/T/'card.txt').read_text() and not (B/'claims'/T/'done.txt').exists()
assert (B/'claims/journal.log').stat().st_size<16*1024**2
latest=[json.loads(row) for row in (B/'claims/journal.log').read_text().splitlines() if json.loads(row).get('task')==T]
assert latest and latest[-1]['event'] not in ['done','blocked']
old=json.loads((D/'active_cpu_wave.json').read_text());assert old['wave']==6
assert not (W/'wave7-scope.json').exists() and not (D/'wave7-launches.jsonl').exists()
launches=[json.loads(row) for row in (D/'wave6-launches.jsonl').read_text().splitlines()]
assert len(launches)==20 and all((D/'out'/r['name']/'result.json').exists() for r in launches)
for path,digest in [(B/'reports'/f'{T}-wave6-report.md','03fe1b076da586c935802bdd249c0d98c6a14c91cc9496181ae4d33c9cab0e34'),
 (D/'wave6.tar.gz','cc8cb47d5d0983a907974948ba762cb90c1738d308787d326f582d326c8d32fe'),
 (D/'wave6-summary.json','0b68d7dde0fb2e3b64e19c395200652efd148d0bf13403c1a9100c785eed9121')]:assert sha(path)==digest
processes=subprocess.check_output(['ps','-eo','pid,args'],text=True).splitlines();assert len(processes)<20000
assert not any(str(D) in row and any(x in row for x in ['sonic_grasp.py','render_verified_replay.py','generate_cpu.py']) for row in processes)
actual=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0])
assert actual+20*16*1024**2+320*1024**2<3*1024**3
assert shutil.disk_usage(D).free>30*1024**3
probe=D/'wave7-write-probe.bin'
if not probe.exists():
    with probe.open('xb') as f:f.write(b'\0'*1024**2)
assert probe.stat().st_size==1024**2
assert probe.read_bytes()==b'\0'*1024**2
# This one generated MiB is deliberately retained and covered by the budget.
wrapper=D/'run.wave7.sh';entry_source=D/'ardy-server-entry.wave7.sh'
assert sha(wrapper)==a.wrapper_sha and sha(entry_source)==a.entry_sha
assert b'\r' not in wrapper.read_bytes() and b'\r' not in entry_source.read_bytes()
entry=B/f'ardy-grasp-run-{T}.sh'
assert sha(D/'run.sh')=='23694e2f49e85f504bf7dbe59a5526006d6bcd19faad573af83c7a52e2638b77'
assert sha(entry)=='ed99c6e9bc53956c177cb4646eea2c1083da4930a204ce1a1599ea074a357357'
assert sha(D/'ardy-server-entry.sh')==sha(entry)
now=datetime.datetime.now().astimezone().isoformat()
scope=dict(old,wave=7,time=now,data_budget_GiB=3,estimated_data_bytes_before=actual,
 plan='First matched no-grip3.14 for new zero-table-contact route, fresh-process repeats in both runtimes; then manifest-selected different text reach_s43 and contact-qualified SETDOWN; collect actual full-loop latency, not policy-only timing; genuine human text correction only if received.',
 storage_change='No budget increase; cumulative3GiB. Retain old20 ledger/archives.20*16MiB new raw plus320MiB checkpoint reserve; no shared downloads/deletion.',
 prior_wave='Wave6 sealed20, paired one positive each, no-grip327 exact pre-intervention, no generalization/controlled placing/real robot claim',
 previous_turn_classification='Interrupted continuation before this turn had read-only preflight and no new tests/code; no progress. Concrete next action is scoped wave7 registration and actual negative trial.',
 wrapper_sha256=a.wrapper_sha,shared_entry_sha256=a.entry_sha,rules_sha256=rules)
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
receipt_path=L/'wave7-scope-receipt.txt'
resumed=receipt_path.exists()
if resumed:
    assert receipt_path.stat().st_size<4096
    receipt_text=receipt_path.read_text()
else:
    receipt=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
     '前一中断轮仅只读取证无新实验，按no-progress恢复。第六波20全部退出、双端SHA封存且7d11dc6自有Git留档；登记第七波<=20次4CPU/AS16/300s/90s，仍累计3GiB，不增预算不覆旧账本。先新路线3.14 no-grip和两版重复，再不同文本reach_s43及受控放置，官方SONIC身体输出不覆盖。规约回到9e2c073c，主会话分段完整复读到EOF，截断末部再拆段重读；只恢复标题排版，未修改共享规约。用户允许直接服务器部署，计划唯一自有根入口改为当前波status；不覆盖vendor/KIMODO/环境/GPU。'],cwd=B,env=env,capture_output=True,text=True,timeout=60)
    receipt_text=receipt.stdout+receipt.stderr;receipt_path.write_text(receipt_text)
    assert receipt.returncode==0,(receipt.returncode,receipt_text)
match=re.search(r'OK journal #(\d+) task='+T+r' event=note',receipt_text);assert match
scope.update(preregistration_journal_number=int(match.group(1)),resumed_after_receipt_channel_failure=resumed)
(W/'wave7-scope.json').write_text(json.dumps(scope,indent=2)+'\n')
shutil.copy2(D/'active_cpu_wave.json',W/'wave6-active-scope.before-wave7.json')
shutil.copy2(D/'run.sh',W/'run.sh.before-wave7');shutil.copy2(entry,W/'shared-entry.before-wave7.sh')
for target,source in [(D/'run.sh',wrapper),(entry,entry_source),(D/'ardy-server-entry.sh',entry_source)]:
    temporary=target.with_name(target.name+'.wave7-install');assert not temporary.exists()
    with temporary.open('xb') as f:f.write(source.read_bytes())
    os.chmod(temporary,target.stat().st_mode&0o777);os.replace(temporary,target)
    assert sha(target)==sha(source)
temporary=D/'active_cpu_wave.wave7-install.json';assert not temporary.exists()
temporary.write_text(json.dumps(scope,indent=2)+'\n');os.replace(temporary,D/'active_cpu_wave.json')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave7_scope='+json.dumps(scope,ensure_ascii=False)+'\n')
with (B/'claims'/T/'rules_seen_after').open('a') as f:f.write(rules+'  '+str(B/'AGENTS.md')+'\n')
(W/'rules-read-wave7-9e2c073c.md').write_text('# Rules refresh '+now+'\nCurrent SHA='+rules+'; reverted to previously read canonical9e2c version.\nMain agent fully reread1-180/181-360/361-540/541-640/641-EOF; initial aggregated end was truncated and repeated. Shared AGENTS not modified. Prior68db was title-format-only; no substantive scope change.\n')
confirmed=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
 f'更正journal#{match.group(1)}：该次只完成第七波计划登记；回执成功正文在stderr，旧检查只看stdout触发AssertionError，当时active仍wave6、根入口未换、物理启动0。现核对原成功回执后恢复，不重复原登记，已实际切换自有根status入口及active到wave7。<=20启动4CPU/AS16/300s/90s、累计3GiB不增；旧20全部保留。当前规则9e2c完整复读，目标ACTIVE，下一步真实同源3.14 no-grip。',
 '--field','voids='+match.group(1)],cwd=B,env=env,capture_output=True,text=True,timeout=60)
confirmed_text=confirmed.stdout+confirmed.stderr
(L/'wave7-registration-confirmed.txt').write_text(confirmed_text)
assert confirmed.returncode==0 and 'OK journal #' in confirmed_text,(confirmed.returncode,confirmed_text)
with (L/'steps.md').open('a') as f:
    f.write('\n## [WAVE7 RENEWAL / RULES REFRESH] '+now+'\n'+receipt_text+confirmed_text+
      '-No physics launched by registration. Prior20 all result files exist and no matching live own processes.\n'+
      '-Data bytes='+str(actual)+'; retained real1MiB write probe;20*16MiB+320MiB checkpoint below cumulative3GiB. /home small texts only.\n'+
      '-Read AGENTS1-180/181-360/361-540/541-640/641-EOF; aggregated541-EOF truncation repeated independently. Current9e2c accepted, shared AGENTS untouched.\n'+
      '-Earlier speculative generation.json read returned No such file; actual generated_phases2/summary.json read successfully. No lost-data claim.\n'+
      '-First registration failed assert OK journal in stdout after real writer success in stderr; read exact receipt and active wave6 before resuming; previous statement superseded with voids field. No blind duplicate.\n'+
      '-Unique root entry status reads active ledger, historical evidence still available.\n')
for path in D.iterdir():
    if path.is_file() and path.suffix in {'.py','.sh'}:shutil.copy2(path,W/path.name)
print(json.dumps(dict(scope=scope,receipt=receipt_text,confirmed_receipt=confirmed_text,shared_entry=str(entry),physical_steps=0,maxrss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),indent=2))
