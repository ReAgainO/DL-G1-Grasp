from pathlib import Path
import subprocess,json,hashlib
r=Path('/data/group4/20261008-202654-codex-182c4568/frozen32');a=r.parent/'archive';a.mkdir(exist_ok=True)
assert not (r/'.git').exists();subprocess.run(['git','init','-b','main',str(r)],check=True,capture_output=True)
paths=[str(p.relative_to(r)) for p in r.glob('*.py')]+['FROZEN-MANIFEST.json','start_frozen32.sh']+[str(p.relative_to(r)) for p in (r/'official_refs').rglob('*') if p.is_file()]
paths += [str(p.relative_to(r)) for p in (r/'out').rglob('*') if p.is_file() and ('native_' in str(p.relative_to(r)) or p.name=='surface_exec25_plan.json')]
subprocess.run(['git','-C',str(r),'add','--',*sorted(set(paths))],check=True)
cfg=['git','-C',str(r),'-c','user.name=Codex ReAgain0','-c','user.email=01a11763-05ca-7133-811e-3b4f81f35331@worker00039.invalid']
z=subprocess.run(cfg+['commit','-m','Freeze native-derived G1 Dex3 full physical grasp controller 32'],check=True,capture_output=True,text=True)
commit=subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()
bundle=a/'frozen32.bundle';subprocess.run(['git','-C',str(r),'bundle','create',str(bundle),'--all'],check=True,capture_output=True);subprocess.run(['git','-C',str(r),'bundle','verify',str(bundle)],check=True,capture_output=True)
manifest=json.loads((r/'FROZEN-MANIFEST.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt={'task':'20261008-202654-codex-182c4568','source_commit':commit,'source_email':'01a11763-05ca-7133-811e-3b4f81f35331@worker00039.invalid','bundle_sha256':sha(bundle),'bundle_bytes':bundle.stat().st_size,'frozen_manifest_sha256':sha(r/'FROZEN-MANIFEST.json'),'frozen_core_files':len(manifest['manifest_files']),'large_assets':'Models/meshes/pydeps copied in frozen32 but excluded from Git bundle; exact hashes retained; external interpreters/ARDY weights remain readonly dependencies. Persistent server copies are not off-server backups.','report_archive':'local only as expressly chosen by user; no report documents uploaded','scope':'fixed35mm/base-.06 scene; repaired native not unmodified ARDY','positive':['normal_trial32','normal_trial32_repeat1'],'negative':'negative_trial32','all_own_physics_jobs_exited':all(not Path('/proc/'+str(p)).exists() for p in [3691938,3707086,3707157])}
(a/'freeze32-receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
