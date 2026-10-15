from pathlib import Path
import shutil,json,hashlib
r=Path('/data/group4/20261008-202654-codex-182c4568/rep');d=r.parent/'frozen32';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();old=json.loads((d/'FROZEN-MANIFEST.json').read_text());pos=json.loads((r/'out/normal_trial32/result.json').read_text())
for n,v in old['manifest_files'].items():assert sha(d/n)==v,n
for n,v in pos['runtime']['source_sha'].items():
 p=d/(n+'.py')
 if not p.exists():shutil.copy2(r/p.name,p)
 assert sha(p)==v,n
for n,v in pos['runtime']['sonic_weights'].items():assert sha(d/'sonic_v11'/n)==v,n
old['manifest_files']={str(p.relative_to(d)):sha(p) for p in sorted(d.rglob('*')) if p.is_file() and p.name!='FROZEN-MANIFEST.json'};old['source_stamp_matches']=True;old['complete']=True;(d/'FROZEN-MANIFEST.json').write_text(json.dumps(old,indent=2))
print(json.dumps({'file_count':len(old['manifest_files']),'complete':True,'manifest_sha256':sha(d/'FROZEN-MANIFEST.json')}))
