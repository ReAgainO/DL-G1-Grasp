"""Bounded read-only localization of measured robot/table contacts."""
import argparse
import csv
import gzip
import json
from pathlib import Path
from wave4_records import sha

p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(name).name==name and len(name)<128 for name in [a.episode,a.output])
folder=root/'out'/a.episode;dest=root/'out'/a.output;assert dest.suffix=='.json' and not dest.exists()
r=json.loads((folder/'result.json').read_text());path=folder/'robot_support_contacts.csv.gz'
groups={};total=0;loaded=0
with gzip.open(path,'rt') as f:
    stamp=f.readline();assert json.loads(stamp.split('=',1)[1])==r['runtime_stamp']
    for row in csv.DictReader(f):
        total+=1;assert total<=1440000
        force=float(row['normal_force_N'])
        if row['support_geom_name']!='table_top' or force<=.001:continue
        loaded+=1;key=row['phase']+' / '+row['robot_body']+' / '+row['robot_geom_name']
        t=float(row['time_s']);distance=float(row['distance_m'])
        record=groups.setdefault(key,dict(phase=row['phase'],robot_body=row['robot_body'],
            robot_geom=row['robot_geom_name'],rows=0,first_time_s=t,last_time_s=t,peak_normal_N=0.,min_distance_m=0.))
        record['rows']+=1;record['last_time_s']=t;record['peak_normal_N']=max(record['peak_normal_N'],force)
        record['min_distance_m']=min(record['min_distance_m'],distance)
answer=dict(physical_steps=0,episode=a.episode,runtime_stamp=r['runtime_stamp'],
    script_sha256=sha(__file__),result_sha256=sha(folder/'result.json'),contact_source_sha256=sha(path),
    contact_rows_examined=total,loaded_robot_table_rows=loaded,by_phase_body_geom=groups,
    full_task_table_max_N=r['balance_audit_summary']['robot_table_all_max_normal_N'],
    strict_success=r['success'],failed_gates=[key for key,value in r['gates'].items() if not value],
    actual_clearance=r['clearance_approach'],native_branch=r['post_clearance_native_branch'],
    limitation='Original solver contact localization, not replay-image contact inference or causal intervention; contact rows are not independent events or per-step force sums.')
dest.write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
