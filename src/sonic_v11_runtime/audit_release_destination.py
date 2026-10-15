"""Audit actual final support geom from recorded solver contacts, not images."""
import argparse
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path
import mujoco
import numpy as np

p=argparse.ArgumentParser();p.add_argument('episodes',nargs='+');a=p.parse_args()
root=Path(__file__).resolve().parent
assert len(a.episodes)<=20
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
for name in a.episodes:
    assert Path(name).name==name and name not in ['.','..']
    folder=root/'out'/name;dest=folder/'release-destination.json';assert not dest.exists()
    r=json.loads((folder/'result.json').read_text());meta=json.loads((folder/'contact-audit.json').read_text())
    tele=np.loadtxt(folder/'telemetry.csv.gz',delimiter=',',comments='#');assert len(tele)<=45000
    final_contacts=[]
    with gzip.open(folder/'cube_contacts.csv.gz','rt') as f:
        next(f);columns=next(f).removeprefix('# ').strip().split(',')
        for i,row in enumerate(csv.DictReader(f,fieldnames=columns)):
            assert i<45000*128
            if float(row['time_s'])<r['duration_s']-.02 or float(row['contact_fn_N'])<=.001:continue
            g=meta['geom_metadata'][str(int(float(row['other_geom'])))]
            final_contacts.append(dict(time_s=float(row['time_s']),geom=g['name'],body=g['body_name'],
                category=g['category'],normal_N=float(row['contact_fn_N'])))
    supports={c['geom'] for c in final_contacts if c['category']=='support'}
    stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
        dt=r['runtime_stamp']['dt'],model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=sha(__file__),
        library_sha={'episode':sha(folder/'result.json'),'raw_contacts':sha(folder/'cube_contacts.csv.gz'),
            'telemetry':sha(folder/'telemetry.csv.gz')})
    answer=dict(runtime_stamp=stamp,source_episode_runtime_stamp=r['runtime_stamp'],physical_steps=0,
        source_episode=name,final_cube_position_m=tele[-1,1:4].tolist(),final_support_geoms=sorted(supports),
        final_table_supported='table_top' in supports,final_floor_supported='floor' in supports,
        final_contacts=final_contacts,legacy_final_supported=r['gates']['final_supported'],
        definition='Last 20ms of original solver contacts >.001N; legacy gate does not distinguish floor/table. No historical result is rewritten.')
    dest.write_text(json.dumps(answer,indent=2)+'\n')
    print(json.dumps({k:v for k,v in answer.items() if k not in ['runtime_stamp','source_episode_runtime_stamp','final_contacts']}))
