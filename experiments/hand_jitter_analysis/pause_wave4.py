"""Repair premature wave overlap using only verified own PID identities."""
from pathlib import Path
import datetime,json,os,signal,sys
R=Path('/data/group4/20261009-170228-codex-fcd727b9')
B=Path('/home/group4/group4_dasc7606c')
ids=[638951,638953,638955,638956,638949,638950,638952,638954,638944]
action=sys.argv[1]
if action=='pause':
    rows=[]
    for pid in ids:
        p=Path('/proc')/str(pid)
        command=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
        cwd=str((p/'cwd').resolve())
        ticks=(p/'stat').read_text().split()[21]
        assert str(R) in command and cwd==str(R),(pid,command,cwd)
        assert 'execute_jitter.py' in command or ('run_wave.py run wave4' in command)
        rows.append({'pid':pid,'command':command,'cwd':cwd,'ticks':ticks})
    for row in rows:
        p=Path('/proc')/str(row['pid'])
        assert (p/'stat').read_text().split()[21]==row['ticks']
        os.kill(row['pid'],signal.SIGSTOP)
    report={'time':datetime.datetime.now().astimezone().isoformat(),'reason':'wave4 launched prematurely after wave3-evaluation missing-done assertion; four-wave4 workers paused, no peer processes touched','rows':rows}
    with (R/'configs/wave4-paused.json').open('x') as f:json.dump(report,f,indent=2)
elif action=='resume':
    assert (R/'configs/wave3-done.json').exists()
    report=json.loads((R/'configs/wave4-paused.json').read_text())
    for row in report['rows']:
        p=Path('/proc')/str(row['pid'])
        assert (p/'stat').read_text().split()[21]==row['ticks']
        assert str((p/'cwd').resolve())==row['cwd']
        assert (p/'cmdline').read_bytes().replace(b'\0',b' ').decode()==row['command']
    for row in reversed(report['rows']):os.kill(row['pid'],signal.SIGCONT)
    report={'time':datetime.datetime.now().astimezone().isoformat(),'reason':'wave3 done verified, resume same own PID identities','pids':[r['pid'] for r in report['rows']]}
    with (R/'configs/wave4-resumed.json').open('x') as f:json.dump(report,f,indent=2)
else:raise ValueError(action)
with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- Scheduling correction '+json.dumps(report)+'\n')
print(json.dumps(report))
