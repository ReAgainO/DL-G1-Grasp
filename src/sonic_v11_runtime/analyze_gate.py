"""Read-only analysis of why a preclosure gate does not dwell."""
import argparse,json
from pathlib import Path
import numpy as np
import sonic_v11 as s
root=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args();folder=root/'out'/a.name
r=json.loads((folder/'result.json').read_text());csv=folder/r.get('telemetry_schema',{}).get('path','telemetry.csv');rows=np.loadtxt(csv,delimiter=',',comments='#')
out=folder/'offline-gate.json';assert not out.exists()
start=next(e['time_s'] for e in r['events'] if e['phase']=='ALIGN');x=rows[rows[:,0]>=start];conditions={
 'one_pad_force':(x[:,7:10]>.05).any(axis=1),
 'position_35mm':x[:,14]<.035,'flat_15mm':x[:,15]<.015,
 'contact_close_candidate':(x[:,7:10]>.05).any(axis=1)&(x[:,14]<.035)&(x[:,15]<.015)}
stats={}
for key,c in conditions.items():
 runs=[];run=0
 for val in c:
  run=run+1 if val else 0;runs.append(run)
 stats[key]=dict(ticks=int(c.sum()),longest_dwell_s=float(max(runs,default=0)*.002),first_time_s=float(x[np.flatnonzero(c)[0],0]) if c.any() else None)
result=dict(source_runtime_stamp=r['runtime_stamp'],physical_steps=0,telemetry_sha=s.sha(csv),candidate_statistics=stats,min_position_error_m=float(x[:,14].min()),min_pad_spread_m=float(x[:,15].min()),one_finger_max_force_N=float(x[:,7:10].max()))
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
