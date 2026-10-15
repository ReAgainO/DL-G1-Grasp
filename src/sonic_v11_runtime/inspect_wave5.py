"""Bounded read-only fifth-wave physical and contact summary."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('names', nargs='*')
args=parser.parse_args()
launches=[json.loads(line) for line in (root/'wave5-launches.jsonl').read_text().splitlines()]
assert len(launches)<=20
assert not args.names or set(args.names).issubset({launch['name'] for launch in launches})
if args.names:
    launches=[launch for launch in launches if launch['name'] in args.names]
for launch in launches:
    folder=root/'out'/launch['name']
    path=folder/'result.json'
    if not path.exists():
        print(json.dumps(dict(name=launch['name'],pending_result=True)))
        continue
    r=json.loads(path.read_text())
    keys=['success','fail_reason','duration_s','wall_s','max_lift_m','hold_min_lift_m','hold_slip_m','hold_min_contact_bodies','max_drift_m','min_up_z','whole_body_balance_validated','actual_to_decoded_motor_target_rms_rad','table_front_x_m','phase_clips_consumed']
    compact={key:r.get(key) for key in keys}
    compact.update(name=launch['name'],version=r['runtime_stamp']['mujoco_version'],
        failed_gates=[k for k,v in r['gates'].items() if not v],balance=r['balance_audit_summary'])
    rows=np.loadtxt(folder/'telemetry.csv.gz',delimiter=',',comments='#')
    assert len(rows)<=45000
    phase_details=[]
    for i,event in enumerate(r['events']):
        if event['phase'] not in ['CLOSE','LIFT','HOLD','SETDOWN','RELEASE']:
            continue
        end=r['events'][i+1]['time_s'] if i+1<len(r['events']) else r['duration_s']
        mask=(rows[:,0]>event['time_s'])&(rows[:,0]<=end)
        part=rows[mask]
        if not len(part):
            continue
        pads=(part[:,7:10]>.01).sum(axis=1)
        two=(pads>=2)&(part[:,10]<.001)
        longest=count=0
        for v in two:
            count=count+1 if v else 0
            longest=max(longest,count)
        phase_details.append(dict(phase=event['phase'],duration_s=len(part)*.002,
            total_two_pad_no_support_s=float(two.sum()*.002),longest_two_pad_no_support_s=longest*.002,
            max_pad_contacts=int(pads.max()),cube_z_min_m=float(part[:,3].min()),
            cube_z_max_m=float(part[:,3].max()),support_max_N=float(part[:,10].max())))
    compact['phase_contact_details']=phase_details
    raw=folder/'robot_support_contacts.csv.gz'
    contacts={}
    if raw.exists():
        with gzip.open(raw,'rt') as f:
            next(f)
            for number,row in enumerate(csv.DictReader(f)):
                assert number<1440000
                force=float(row['normal_force_N'])
                if force<=.001:
                    continue
                key=row['phase']+'/'+row['robot_body']+'/'+row['support_geom_name']
                record=contacts.setdefault(key,dict(loaded_contacts=0,max_per_contact_normal_N=0.))
                record['loaded_contacts']+=1
                record['max_per_contact_normal_N']=max(record['max_per_contact_normal_N'],force)
    compact['robot_support_contact_pairs']=contacts
    print(json.dumps(compact,ensure_ascii=False))
