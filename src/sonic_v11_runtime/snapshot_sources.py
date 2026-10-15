"""Immutable task-local source snapshots before each bounded execution."""
import hashlib,json,shutil,uuid
from pathlib import Path
root=Path(__file__).resolve().parent;directory=root/'source-snapshots';directory.mkdir(exist_ok=True);items=[]
for source in sorted([*root.glob('*.py'),*root.glob('*.sh')]):
 if source.stat().st_size>2*1024**2:raise ValueError('Unexpected source file >2MiB')
 digest=hashlib.sha256(source.read_bytes()).hexdigest();folder=directory/digest;folder.mkdir(exist_ok=True)
 target=folder/source.name
 if not target.exists():shutil.copy2(source,target)
 assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
 items.append(dict(path=str(source),sha256=digest,snapshot=str(target)))
manifest=directory/('manifest-'+uuid.uuid4().hex+'.json');manifest.write_text(json.dumps(items,indent=2)+'\n')
print('SOURCE_SNAPSHOT='+str(manifest))
