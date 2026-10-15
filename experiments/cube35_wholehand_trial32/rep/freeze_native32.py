from pathlib import Path
import ast,shutil,json,hashlib
r=Path('/data/group4/20261008-202654-codex-182c4568/rep');d=r.parent/'frozen32';d.mkdir(exist_ok=False)
queue=['normal_runner32','negative_replay32','ardy_native22','native_profile28','native_profile29','native_profile30','native_fk22','prepare_native22','surface_entry25','surface_path22','surface_route22','coupled_surface_plan'];seen=set()
while queue:
 mod=queue.pop()
 if mod in seen or not (r/(mod+'.py')).is_file():continue
 seen.add(mod);p=r/(mod+'.py');shutil.copy2(p,d/p.name)
 tree=ast.parse(p.read_text())
 for node in ast.walk(tree):
  names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
  for name in names:
   top=name.split('.')[0]
   if (r/(top+'.py')).is_file():queue.append(top)
for name in ['src','official_refs','sonic_v11','pydeps']:shutil.copytree(r/name,d/name)
(d/'out').mkdir()
for name in ['surface_exec25_plan.json']:shutil.copy2(r/'out'/name,d/'out'/name)
for name in ['native_ardy22','native_profile28','native_profile29','native_profile30']:shutil.copytree(r/'out'/name,d/'out'/name)
# Read-only seed scene/first trajectory used by the profile compiler; do not include calibration successes as current verification.
(d/'out/normal_trial27').mkdir()
for name in ['scene.xml','g1_free_grasp.xml','trajectory.npz']:shutil.copy2(r/'out/normal_trial27'/name,d/'out/normal_trial27'/name)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files={str(p.relative_to(d)):sha(p) for p in sorted(d.rglob('*')) if p.is_file()}
manifest={'release':'frozen32','positive_run':'normal_trial32','source_dir':str(r),'controller_modules':sorted(seen),'manifest_files':files,'scope':'frozen native-derived physical controller and inputs; not untouched raw ARDY; official model/assets copied unchanged; external Python environments and ARDY vendor/text/weights remain readonly dependencies','reports_uploaded':False}
(d/'FROZEN-MANIFEST.json').write_text(json.dumps(manifest,indent=2))
# Validate all copied files against original controller stamp/weights/profile.
pos=json.loads((r/'out/normal_trial32/result.json').read_text())
for name,v in pos['runtime']['source_sha'].items():assert sha(d/(name+'.py'))==v,name
for name,v in pos['runtime']['sonic_weights'].items():assert sha(d/'sonic_v11'/name)==v,name
assert sha(d/'out/native_profile30/profile.npz')==pos['ardy_consumption']['profile_sha256']
print(json.dumps({'release':str(d),'file_count':len(files),'modules':len(seen),'manifest_sha256':sha(d/'FROZEN-MANIFEST.json'),'source_stamp_matches':True}))
