"""Read-only500Hz retention/table-bearing audit; no final-state shortcut."""
import argparse,csv,gzip,json
from pathlib import Path
import mujoco,numpy as np
from wave4_records import sha
p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');a=p.parse_args()
root=Path(__file__).resolve().parent
assert all(Path(n).name==n and len(n)<128 for n in [a.episode,a.output])
folder=root/'out'/a.episode;r=json.loads((folder/'result.json').read_text());assert r['setdown_enabled']
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
m=mujoco.MjModel.from_xml_path(str(folder/'scene.xml'));dt=float(m.opt.timestep);table=m.geom('table_top').id;cube=m.body('red_cube').id
with gzip.open(folder/'telemetry.csv.gz','rt') as f:
 assert json.loads(f.readline().split('=',1)[1])==r['runtime_stamp'];columns=f.readline().strip().removeprefix('# ').split(',')
 rows=list(csv.reader(f));assert 1<=len(rows)<=45000;values=np.asarray(rows,dtype=float)
assert values.shape==(len(rows),len(columns)) and np.isfinite(values).all();lookup={n:i for i,n in enumerate(columns)}
table_load=np.zeros(len(rows));contact_rows=0
with gzip.open(folder/'cube_contacts.csv.gz','rt') as f:
 assert json.loads(f.readline().split('=',1)[1])==r['runtime_stamp'];header=f.readline().strip().removeprefix('# ').split(',')
 for row in csv.DictReader(f,fieldnames=header):
  contact_rows+=1;assert contact_rows<=1440000
  step=int(float(row['step']));assert 0<=step<len(rows)
  if int(float(row['other_geom']))==table:table_load[step]+=max(0,float(row['contact_fn_N']))
times=values[:,lookup['time_s']];event={e['phase']:e['time_s'] for e in r['events']}
assert 'SETDOWN' in event
start=event['SETDOWN'];end=event.get('RELEASE',r['duration_s']);mask=(times>start+dt/2)&(times<=end+dt/2)
idx=np.where(mask)[0];assert len(idx)>0
opposed=(values[:,lookup['thumb_force_N']]>.01)&(values[:,lookup['middle_force_N']]>.01)
first=np.where(mask&(table_load>.05))[0];first_i=int(first[0]) if len(first) else None
retained=idx[idx<first_i] if first_i is not None else idx
longest=run=0
for good in opposed[retained]:
 run=0 if good else run+1;longest=max(longest,run)
relative=values[retained,4:7];slip=float(np.max(np.linalg.norm(relative-relative[0],axis=1))) if len(relative) else None
weight=float(m.body_mass[cube]*np.linalg.norm(m.opt.gravity));last_idx=np.where((times>end-.2)&(times<=end+dt/2))[0]
release_idx=last_idx if 'RELEASE' in event else np.array([],dtype=int)
bearing_min=float(table_load[release_idx].min()) if len(release_idx) else None
answer=dict(runtime_stamp=r['runtime_stamp'],physical_steps=0,episode=a.episode,script_sha256=sha(__file__),
 result_sha256=sha(folder/'result.json'),telemetry_sha256=sha(folder/'telemetry.csv.gz'),contacts_sha256=sha(folder/'cube_contacts.csv.gz'),
 physics_samples=len(rows),contact_rows=contact_rows,setdown_start_s=start,release_s=event.get('RELEASE'),
 first_table_contact_s=float(times[first_i]) if first_i is not None else None,retention_samples=len(retained),
 opposed_load_threshold_N=.01,opposed_loaded_fraction_before_table=float(opposed[retained].mean()) if len(retained) else None,
 longest_opposed_load_gap_before_table_s=longest*dt,pre_table_cube_wrist_slip_mm=slip*1000 if slip is not None else None,
 cube_weight_N=weight,table_min_last200ms_before_release_N=bearing_min,
 table_min_last200ms_at_stop_N=float(table_load[last_idx].min()) if len(last_idx) else None,
 continuous_opposed_load_before_table=bool(len(retained) and opposed[retained].all()),
 table_bearing_before_release=bool('RELEASE' in event and bearing_min is not None and bearing_min>=.8*weight),
 strict_episode_success=r['success'],failed_gates=[k for k,v in r['gates'].items() if not v],fail_reason=r['fail_reason'],
 final_table_supported=r['gates'].get('final_table_supported'),
 limitation='Observes original500Hz solver contact forces and wrist-relative motion. Exact continuous-load criterion may detect chatter; final table support alone never certifies controlled placement. No new dynamics or force-closure/vision certificate.')
answer['controlled_placing_observed']=bool(answer['strict_episode_success'] and answer['continuous_opposed_load_before_table'] and answer['table_bearing_before_release'] and slip is not None and slip<=.01)
dest=root/'out'/a.output;assert dest.suffix=='.json'
with dest.open('x') as f:f.write(json.dumps(answer,indent=2)+'\n')
print(json.dumps({k:v for k,v in answer.items() if k!='runtime_stamp'},indent=2))
