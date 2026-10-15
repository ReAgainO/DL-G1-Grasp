"""Atomic launch-count guard; locks only this task's own bounded CPU wave."""
import datetime
import fcntl
import json
import subprocess
import sys
from pathlib import Path

def reserve(root, script, name):
    scope = json.loads((root/'active_cpu_wave.json').read_text())
    assert scope['task'] == root.name == '20261006-093203-codex-6385a841'
    assert scope['wave'] >= 5 and scope['max_physical_script_launches'] == 20
    assert Path(script).resolve() == root/'sonic_grasp.py'
    assert Path(name).name == name and name.startswith(f"w{scope['wave']}_")
    assert not (root/'out'/name).exists(), 'Output already exists; no overwrite'
    actual = int(subprocess.check_output(['du','-sb',str(root)], text=True).split()[0])
    assert actual+16*1024**2 < scope['data_budget_GiB']*1024**3, 'Task data budget exhausted'
    ledger = root/f"wave{scope['wave']}-launches.jsonl"
    with (root/f"wave{scope['wave']}-launch.lock").open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lines = ledger.read_text().splitlines() if ledger.exists() else []
        assert len(lines) < scope['max_physical_script_launches'], 'Wave launch budget exhausted'
        assert not any(json.loads(line)['name'] == name for line in lines), 'Launch name reserved already'
        record = dict(task=scope['task'],wave=scope['wave'],launch=len(lines)+1,name=name,
                      time=datetime.datetime.now().astimezone().isoformat(),
                      definition='One script launch, counted even if physics startup later fails',
                      task_data_logical_bytes_before=actual)
        with ledger.open('a') as stream:
            stream.write(json.dumps(record)+'\n')
    return record

if __name__ == '__main__':
    print(json.dumps(reserve(Path(__file__).resolve().parent, sys.argv[1], sys.argv[2])))
