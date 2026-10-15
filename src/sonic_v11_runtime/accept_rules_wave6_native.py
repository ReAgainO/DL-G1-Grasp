"""Record a fully read, exact rule revision; never modify the shared rules."""
import datetime
import difflib
import hashlib
import json
import resource
import subprocess
from pathlib import Path

resource.setrlimit(resource.RLIMIT_AS, (16 * 1024**3, 16 * 1024**3))
T = '20261006-093203-codex-6385a841'
B = Path('/home/group4/group4_dasc7606c')
D = Path('/data/group4') / T
expected = '68db8493e678a0cab6613610a8d87f4fca6597f8369ccd5a75cea089bfd41db6'
raw = (B / 'AGENTS.md').read_bytes()
assert hashlib.sha256(raw).hexdigest() == expected, 'Rules drifted again; read difference first'
card = (B / 'claims' / T / 'card.txt').read_text()
assert '745a0dbc-a26f-4c01-add8-7577fca612de' in card
events = [json.loads(line) for line in (B / 'claims/journal.log').read_text().splitlines()]
own = [e for e in events if e['task'] == T]
assert own and own[-1]['event'] not in ('done', 'blocked')
old = subprocess.check_output(['git', '-C', str(B), 'show', '0d6b84c2434bef0b0a26a7d5840bf973a848a52b:AGENTS.md']).decode()
diff = ''.join(difflib.unified_diff(old.splitlines(True), raw.decode().splitlines(True), fromfile='checkpoint-rules', tofile='current-rules'))
assert diff.count('@@') == 2 and '规约' not in diff.split('@@')[-1].splitlines()[-1], 'Unexpected rule changes require review'
out = B / 'work' / T / ('rules-read-' + expected[:12] + '.md')
assert not out.exists()
now = datetime.datetime.now().astimezone().isoformat()
out.write_text('# Exact rule revision reviewed\n' + now + '\nsha256=' + expected + '\n\n```diff\n' + diff + '\n```\n')
with (B / 'claims' / T / 'rules_seen_after').open('a') as f:
    f.write(expected + '  ' + str(B / 'AGENTS.md') + '\n')
with (B / 'logs' / T / 'steps.md').open('a') as f:
    f.write('\n## [rules refresh] ' + now + '\n- All rules read in 3 full chunks; title-only diff reviewed. No shared rule edit.\n- Exact accepted SHA: ' + expected + '\n- Failures: local SSH option typo Bad configuration option: stricthostchecking; fixed Key spelling; wrapper stopped rc9 STOP: collaboration rules changed; no physics launched. Remote rg unavailable; used grep. Repeated read output initially truncated, reread each complete chunk separately.\n- Evidence: ' + str(out) + '; own run.sh guard updated, no scope change.\n')
note = '完整重读新AGENTS并读标题排版差异，接受sha68db8493e678；旧规则闸rc9暂停未启动物理。仍原任务继续，14次启动已退出/严格成功0，余6；分支静态可达但SONIC实际未到位，继续零步诊断和输入端闭环，不改共享规约或vendor。'
subprocess.run(['bash', str(B / 'work/journal/tools2/journal_append.sh'), T, 'note', '-', note], check=True)
print(json.dumps({'rules_sha256': expected, 'review': str(out), 'maxrss_kb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
