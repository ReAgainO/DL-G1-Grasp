"""Register a new bounded hand-jitter task; never reopen the archived batch."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import resource
import secrets
import shutil
import subprocess

resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
B = Path('/home/group4/group4_dasc7606c')
EXPECTED = '9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
SID = '01a0e195-925b-7fa1-b43f-e6f9391253df'
OLD = Path('/data/group4/20261009-021611-codex-415484ce')
now = lambda: datetime.datetime.now().astimezone().isoformat()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(B / 'AGENTS.md') == EXPECTED, 'Rules changed: reread before any write'
assert shutil.disk_usage('/home').free > 100 * 1024**2
assert shutil.disk_usage('/data').free > 42 * 1024**3
T = datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-codex-' + secrets.token_hex(4)
C, W, L, D = B / 'claims' / T, B / 'work' / T, B / 'logs' / T, Path('/data/group4') / T
C.mkdir()
W.mkdir()
L.mkdir()
D.mkdir()
scope = ('Diagnose and reduce successful native-wholehand grasp jitter from frozen own batch; '
         'new-task sources/results only, peers and prior completed tasks readonly; no GPU/realrobot/'
         'object overrides/weld/externalforces; up to4 concurrent2core jobs, AS4GiB/job; '
         'each command <=600s, finite optimization wave <=4h; data peak12GiB, home text<=5MiB; '
         'keep success gate, geometry, gravity, source references and all failed attempts; '
         'high-rate telemetry, physical A/B comparisons and high-frame-rate true-state replay')
with (C / 'card.txt').open('x') as f:
    f.write(f'task={T}\nowner=codex(hp<{SID}>)\nsession_id={SID}\nstarted={now()}\nscope={scope}\ndata={D}\n')
with (C / 'rules_seen').open('x') as f:
    f.write(f'{EXPECTED}  {B / "AGENTS.md"}\n')
with (L / 'steps.md').open('x') as f:
    f.write(f'# {T} hand-jitter investigation steps\n\n'
            f'- {now()} Read current AGENTS.md completely in bounded pages; SHA {EXPECTED}. '
            'Read account README; initial SSH alias lookup failed and sandbox denied network; '
            'authorized turn-scoped network then explicit key connection succeeded. '
            'No private key content or user credentials copied.\n'
            '- Source batch is completed: it will remain readonly.\n')
env = os.environ.copy()
for key in ['JOURNAL', 'ANCHOR', 'GPU_BASE', 'ISSUES_BASE']:
    env.pop(key, None)
env['JOURNAL_BASE'] = str(B)
p = subprocess.run(['bash', str(B / 'work/journal/tools2/journal_append.sh'), T, 'start', '-', scope,
                    '--field', f'owner=codex(hp<{SID}>)', '--field', f'session_id={SID}'],
                   capture_output=True, text=True, env=env, timeout=120)
with (L / 'steps.md').open('a') as f:
    f.write(f'\n- {now()} Official start writer rc={p.returncode}\n```\n{p.stdout}{p.stderr}\n```\n')
assert p.returncode == 0, p.stdout + p.stderr
for name in ['logs', 'out', 'tmp', 'configs', 'source-snapshots', 'analysis']:
    (D / name).mkdir()
probe = D / 'data-write-probe-1MiB.bin'
with probe.open('xb') as f:
    f.write(bytes(1024**2))
    f.flush()
    os.fsync(f.fileno())
assert probe.stat().st_size == 1024**2
with (L / 'steps.md').open('a') as f:
    f.write(f'\n- {now()} Data actual write probe: {probe}, bytes=1048576, SHA={sha(probe)}; retained.\n')
for command in [['df', '-h', '/home', '/data', '/tmp'], ['free', '-g']]:
    r = subprocess.run(command, capture_output=True, text=True, timeout=20)
    with (L / 'steps.md').open('a') as f:
        f.write(f'\n- {now()} Resource probe command={command} rc={r.returncode}\n```\n{r.stdout}{r.stderr}\n```\n')
for kind in ['cpu', 'memory', 'io']:
    with (L / 'steps.md').open('a') as f:
        f.write(f'\n- {now()} PSI {kind}: {Path("/proc/pressure",kind).read_text()}\n')
receipt = {'task': T, 'data': str(D), 'work': str(W), 'logs': str(L),
           'rules_sha': EXPECTED, 'source_batch': str(OLD), 'registered': now(),
           'start_receipt': p.stdout, 'scope': scope}
with (D / 'bootstrap-receipt.json').open('x') as f:
    json.dump(receipt, f, indent=2)
print(json.dumps(receipt), flush=True)
