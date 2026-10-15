"""Locate original non-fingertip cube contact forces by phase; no dynamics."""
import argparse
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path
import mujoco

p=argparse.ArgumentParser();p.add_argument('episode');a=p.parse_args()
assert Path(a.episode).name==a.episode and a.episode not in ['.','..']
root=Path(__file__).resolve().parent;folder=root/'out'/a.episode
dest=folder/'nonpad-phase-diagnosis.json';assert not dest.exists()
r=json.loads((folder/'result.json').read_text())
meta=json.loads((folder/'contact-audit.json').read_text())
rows=[];pairs={}
with gzip.open(folder/'cube_contacts.csv.gz','rt') as f:
    next(f);columns=next(f).removeprefix('# ').strip().split(',')
    for i,row in enumerate(csv.DictReader(f,fieldnames=columns)):
        assert i<45000*128
        if int(float(row['category'])) not in [1,2] or float(row['contact_fn_N'])<=.001:continue
        t=float(row['time_s'])
        phase='SETTLE'
        for event in r['events']:
            if event['time_s']<t-1e-9:phase=event['phase']
        other=str(int(float(row['other_geom'])))
        geom=meta['geom_metadata'][other]
        item=dict(time_s=t,phase=phase,body=geom['body_name'],geom=geom['name'],
            normal_N=float(row['contact_fn_N']),cube_vertical_force_N=float(row['cube_force_z_N']))
        assert len(rows)<100000
        rows.append(item)
        key=phase+'/'+geom['body_name']+'/'+str(geom['name'])
        record=pairs.setdefault(key,dict(loaded_contacts=0,first_time_s=t,last_time_s=t,max_per_contact_normal_N=0.))
        record['loaded_contacts']+=1;record['last_time_s']=t
        record['max_per_contact_normal_N']=max(record['max_per_contact_normal_N'],item['normal_N'])
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    dt=r['runtime_stamp']['dt'],model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=sha(__file__),
    library_sha={'episode':sha(folder/'result.json'),'contact_audit':sha(folder/'contact-audit.json'),
        'raw_contacts':sha(folder/'cube_contacts.csv.gz')})
answer=dict(runtime_stamp=stamp,source_episode_runtime_stamp=r['runtime_stamp'],physical_steps=0,
    loaded_nonpad_pairs=pairs,loaded_contacts=len(rows),records=rows,
    limitation='Original solver contact forces, categorization from episode metadata. Phase reconstructed using strict event-time convention. Not a separate physics episode.')
dest.write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(dict(episode=a.episode,pairs=pairs,loaded_contacts=len(rows)),indent=2))
