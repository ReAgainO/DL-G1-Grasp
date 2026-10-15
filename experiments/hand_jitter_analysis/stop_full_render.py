"""Terminate verified own render groups before projected command-budget overrun."""
from pathlib import Path
import datetime,json,os,signal
R=Path('/data/group4/20261009-170228-codex-fcd727b9');B=Path('/home/group4/group4_dasc7606c')
groups=[670386,670388,670391,670393];rows=[]
for g in groups:
    assert os.getpgid(g)==g
    parent=Path('/proc')/str(g)
    assert str(R/'render_dense.py').encode() in (parent/'cmdline').read_bytes()
    members=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():continue
        try:
            if os.getpgid(int(p.name))!=g:continue
            command=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode();cwd=str((p/'cwd').resolve());ticks=(p/'stat').read_text().split()[21]
            assert str(R) in command and cwd==str(R),(p,command,cwd)
            members.append({'pid':int(p.name),'cmd':command,'cwd':cwd,'ticks':ticks})
        except (FileNotFoundError,ProcessLookupError):pass
    assert members
    rows.extend(members)
for row in rows:assert (Path('/proc')/str(row['pid'])/'stat').read_text().split()[21]==row['ticks']
for g in groups:os.killpg(g,signal.SIGTERM)
receipt={'time':datetime.datetime.now().astimezone().isoformat(),'reason':'25fps full53s rendering at observed throughput projects near/above580s budget. Stop only these verified own render groups, preserve partial outputs, rerender34-53s clip in a new directory. No physics repeats/no data deletions.','groups':groups,'rows':rows}
with (R/'configs/render25-budget-stop.json').open('x') as f:json.dump(receipt,f,indent=2)
with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- '+json.dumps(receipt)+'\n')
print(json.dumps({'groups':groups,'verified_members':len(rows),'reason':receipt['reason']}))
