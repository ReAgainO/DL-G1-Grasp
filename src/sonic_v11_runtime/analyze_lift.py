import argparse,gzip,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args();root=Path(__file__).resolve().parent;out=root/'out'/a.name
r=json.loads((out/'result.json').read_text());z=np.load(out/'trajectory.npz',allow_pickle=False)
with gzip.open(out/'telemetry.csv.gz','rt') as f:x=np.loadtxt(f,delimiter=',')
records=[];startz=x[0,3];events=r['events']
for index,event in enumerate(events):
 end=events[index+1]['time_s'] if index+1<len(events) else x[-1,0]+.01;v=x[(x[:,0]>=event['time_s'])&(x[:,0]<end)];mask=(v[:,7]>.1)&(v[:,9]>.1);longest=current=0
 for okay in mask:current=current+1 if okay else 0;longest=max(longest,current)
 records.append(dict(phase=event['phase'],start=event['time_s'],end=end,min_lift_m=float(v[:,3].min()-startz),max_lift_m=float(v[:,3].max()-startz),
  thumb_middle_contact_seconds=float(mask.sum()*.002),longest_thumb_middle_contact_seconds=longest*.002,max_forces_N=v[:,7:10].max(axis=0).tolist(),
  final_forces_N=v[-1,7:10].tolist(),final_support_N=float(v[-1,10])))
lift_start=next((e['time_s'] for e in events if e['phase']=='LIFT'),1e9);samples=[]
for dt in [0,.2,.5,1.,1.5,2.,3.,4.,6.,8.,9.]:
 t=lift_start+dt;i=int(np.argmin(abs(x[:,0]-t)))
 if t>x[-1,0]:continue
 q=int(np.argmin(abs(z['time']-t)));samples.append(dict(time_s=float(x[i,0]),since_lift_s=dt,lift_m=float(x[i,3]-startz),cube_xyz=x[i,1:4].tolist(),forces_N=x[i,7:10].tolist(),support_N=float(x[i,10]),relative_wrist_xyz=x[i,4:7].tolist(),hand_actual=z['qpos'][q,-14:-7].tolist() if False else None,hand_reference=z['hand_reference'][q].tolist() if 'hand_reference' in z else None))
answer=dict(physical_steps=0,source_episode_result_sha=__import__('hashlib').sha256((out/'result.json').read_bytes()).hexdigest(),phases=records,samples=samples)
dest=out/'lift-analysis.json';assert not dest.exists();dest.write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
