"""Read only process/status/resource snapshot; append own small diagnostic receipt."""
import json,datetime,collections,hashlib,sys,os
from pathlib import Path
R=Path(__file__).resolve().parent;B=Path('/home/group4/group4_dasc7606c')
snapshot={'time':datetime.datetime.now().astimezone().isoformat(),'states':{},'pilots':{},'active':[]}
for path in (R/'state').glob('*.json'):
    if path.name in ['launch.json','lifecycle.json','latest-status.json']:continue
    try:
        row=json.loads(path.read_text());snapshot['states'][row['id']]={key:row.get(key) for key in ['group','status','classification','success','error','video_valid']}
    except Exception as error:snapshot['states'][path.stem]={'error':str(error)}
for path in (R/'pilots').glob('*-receipt.json'):
    snapshot['pilots'][path.stem]=json.loads(path.read_text())
for name in ['PBASE2','PRAND2','PSIZE2','PBACK2']:
    path=R/'out'/name/'result.json'
    if path.exists():
        row=json.loads(path.read_text());snapshot['pilots'][name]={key:row.get(key) for key in ['success','classification','reason','max_lift_m','duration_s','wall_seconds']}
    path=R/'out'/name/'replay/replay.json'
    if path.exists():snapshot['pilots'].setdefault(name,{})['video']=json.loads(path.read_text())
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        command=(proc/'cmdline').read_bytes().decode().replace('\x00',' ')
        if str(R) not in command or 'status_batch.py' in command or not command:continue
        status=(proc/'status').read_text();fields=dict(line.split(':',1) for line in status.splitlines() if ':' in line)
        snapshot['active'].append({'pid':int(proc.name),'command':command,'rss':fields.get('VmRSS','').strip(),
                                   'as':fields.get('VmSize','').strip(),'cores':fields.get('Cpus_allowed_list','').strip()})
    except (OSError,UnicodeDecodeError):pass
snapshot['counts']={group:dict(collections.Counter(row['status'] for row in snapshot['states'].values() if row.get('group')==group)) for group in ['A','B','C','D','NGR','NWS','NGF']}
snapshot['psi']={name:Path('/proc/pressure',name).read_text() for name in ['cpu','memory','io']}
snapshot['rules_sha']=hashlib.sha256((B/'AGENTS.md').read_bytes()).hexdigest()
snapshot['data_bytes']=sum(p.stat().st_size for p in R.rglob('*') if p.is_file() and not p.is_symlink())
path=R/'state/latest-status.json';path.write_text(json.dumps(snapshot,indent=2))
with (B/'logs'/R.name/'steps.md').open('a') as f:
    f.write('\n- '+snapshot['time']+' Read-only status snapshot '+json.dumps(snapshot['counts'])+' active='+str(len(snapshot['active']))+' rules='+snapshot['rules_sha']+'\n')
if '--compact' in sys.argv:
    rows=snapshot['states'].values();finished=[r for r in rows if r.get('status') in ['completed','video_error','infrastructure_error']]
    print(json.dumps({'time':snapshot['time'],'finished':len(finished),'counts':snapshot['counts'],
                      'success':dict(collections.Counter(r['group'] for r in finished if r.get('success'))),
                      'errors':{key:row for key,row in snapshot['states'].items() if row.get('error')},
                      'data_GiB':round(snapshot['data_bytes']/1024**3,3),'active_count':len(snapshot['active']),
                      'ended':(R/'state/lifecycle.json').exists() and 'ended' in json.loads((R/'state/lifecycle.json').read_text()),
                      'rules_sha':snapshot['rules_sha'],'psi_cpu':snapshot['psi']['cpu'].splitlines()[0]}))
elif '--brief' in sys.argv:
    print(json.dumps({'time':snapshot['time'],'counts':snapshot['counts'],'active_count':len(snapshot['active']),
                      'pilot_results':{k:{x:v.get(x) for x in ['success','reason','max_lift_m','classification','wall_seconds']} for k,v in snapshot['pilots'].items() if not k.endswith('receipt')},
                      'pilot_videos':{k:{x:v['video'].get(x) for x in ['frames','duration_s','decode_verified','video_bytes']} for k,v in snapshot['pilots'].items() if 'video' in v},
                      'active':snapshot['active'],'psi':snapshot['psi']},indent=2))
else:print(json.dumps(snapshot,indent=2))
