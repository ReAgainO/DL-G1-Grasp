"""Read existing 500Hz telemetry, distinguishing opposed from same-side contact."""
import csv
import gzip
import json
import sys
from pathlib import Path
from wave4_records import sha

root = Path(__file__).resolve().parent
assert 1 <= len(sys.argv[1:]) <= 20
for name in sys.argv[1:]:
    assert Path(name).name == name
    folder = root/'out'/name
    r = json.loads((folder/'result.json').read_text())
    opponent = 2 if r['opposing_pad'] == 'right_middle_fingertip' else 1
    path = folder/'telemetry.csv.gz'
    phases = {}
    rows = 0
    events = r['events']
    with gzip.open(path, 'rt') as stream:
        stamp_line = stream.readline()
        assert stamp_line.startswith('# runtime_stamp=')
        assert json.loads(stamp_line.split('=',1)[1]) == r['runtime_stamp']
        columns = stream.readline().removeprefix('# ').strip().split(',')
        for cells in csv.reader(stream):
            rows += 1
            assert rows <= 45000
            values = [float(x) for x in cells]
            row = dict(zip(columns,values))
            t = row['time_s']
            phase = next(e['phase'] for e in reversed(events) if t >= e['time_s']-1e-8)
            if phase not in ['ALIGN','CLOSE','LIFT','HOLD','RELEASE']:
                continue
            forces = [row[k] for k in ['thumb_force_N','index_force_N','middle_force_N']]
            stats = phases.setdefault(phase, dict(samples=0, first_time_s=t,last_time_s=t,
                any_two_loaded_samples=0,thumb_and_opponent_loaded_samples=0,
                force_min_N=[1e9]*3,force_max_N=[0.]*3,
                cube_z_min_m=1e9,cube_z_max_m=-1e9,support_max_N=0.))
            stats['samples'] += 1
            stats['last_time_s'] = t
            stats['any_two_loaded_samples'] += sum(x>.01 for x in forces)>=2
            stats['thumb_and_opponent_loaded_samples'] += forces[0]>.01 and forces[opponent]>.01
            stats['force_min_N'] = [min(a,b) for a,b in zip(stats['force_min_N'],forces)]
            stats['force_max_N'] = [max(a,b) for a,b in zip(stats['force_max_N'],forces)]
            stats['cube_z_min_m'] = min(stats['cube_z_min_m'],row['cube_z_m'])
            stats['cube_z_max_m'] = max(stats['cube_z_max_m'],row['cube_z_m'])
            stats['support_max_N'] = max(stats['support_max_N'],row['support_force_N'])
    print(json.dumps(dict(name=name,result_sha256=sha(folder/'result.json'),
        telemetry_sha256=sha(path),physical_steps=0,rows=rows,opposing_pad=r['opposing_pad'],
        phases=phases,legacy_two_finger_gate=r['gates']['two_fingers'],
        limits='Counts from saved solver telemetry, not a force-closure/wrench-feasibility or friction-cone certificate'),indent=2))
