"""Bounded CPU phase generation, using existing weights and private source/cache."""
import datetime,hashlib,json,os,resource,shutil,subprocess,time,sys
from pathlib import Path
B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841';D=Path('/data/group4')/T
OLD=Path('/data/group4/20261006-030300-codex-c87d21ab');PY='/data/group4/20261004-205543-qoder-f5a4a02a/env-gen/bin/python'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
attempt=sys.argv[1] if len(sys.argv)>1 else 'generated_phases'
assert attempt in ['generated_phases','generated_phases2']
out=D/'out'/attempt;assert not out.exists();out.mkdir()
assert sha(OLD/'ardy_probe.py')=='0d879f6c0ec458ed7f9731d7927bb7ea577dc7b424a7bc640549536f73b5818d'
scope=dict(time=datetime.datetime.now().astimezone().isoformat(),cpu4=True,AS_GiB=40,RSS_GiB=24,timeout_s=285,
           purpose='read-only existing 8B text encoder CPU inference, <=4 jobs x4s x25fps; no training/GPU/shared installation',
           previous_physics_AS16_unchanged=True,source_copy_peak_MiB=132,data_total_GiB_limit=1)
(B/'work'/T/('generation-scope-'+attempt+'.json')).write_text(json.dumps(scope,indent=2)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('generation_scope='+json.dumps(scope)+'\n')
with (B/'logs'/T/'steps.md').open('a') as f:f.write('\n## [GEN-PHASES] '+json.dumps(scope)+'\n- AS40/RSS24 is only the 8B CPU generator; physics remains AS16. AvailableRAM941GiB, PSI0; no model copies/downloads.\n- Local syntax check first failed GBK decode, rerun explicit UTF8 passed.\n')
dest=D/'src/ardy_runtime'
if not dest.exists():shutil.copytree(OLD/'src/ardy/ardy',dest/'ardy',ignore=shutil.ignore_patterns('__pycache__','*.pyc'),symlinks=True)
manifest=[]
for p in sorted((dest/'ardy').rglob('*')):
 if p.is_symlink():raise RuntimeError('Runtime source symlink needs explicit provenance '+str(p))
 if p.is_file():
  src=OLD/'src/ardy/ardy'/p.relative_to(dest/'ardy');assert sha(src)==sha(p)
  manifest.append(dict(source=str(src),destination=str(p),sha256=sha(p),bytes=p.stat().st_size))
if not (D/'generator_base.py').exists():shutil.copy2(OLD/'ardy_probe.py',D/'generator_base.py')
assert sha(D/'generator_base.py')==sha(OLD/'ardy_probe.py')
if not (D/'generator-provenance.json').exists():
 (D/'generator-provenance.json').write_text(json.dumps(dict(source_files=manifest,base_generator_sha=sha(D/'generator_base.py'),
                   environment=PY,torch='2.6.0+cpu',offline=True),indent=2)+'\n')
jobs=[dict(stem='reach_s43',seed=43,prompt='A person reaches forward with their right hand to grab a small object on a table.'),
      dict(stem='lift_s42',seed=42,prompt='A standing person slowly lifts a small object upward with their right hand and keeps the left arm relaxed.'),
      dict(stem='hold_s42',seed=42,prompt='A standing person holds a small object steadily in their right hand in front of the chest.'),
      dict(stem='release_s42',seed=42,prompt='A standing person slowly lowers their right hand to place a small object back on a table.')]
(out/'jobs.json').write_text(json.dumps(jobs,indent=2)+'\n')
env=os.environ.copy();env.update(PYTHONPATH=str(dest),PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',
 OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
 HF_HOME=str(D/'cache'),HF_HUB_CACHE=str(D/'cache/hub'),TRANSFORMERS_OFFLINE='1',HF_HUB_OFFLINE='1',
 TMPDIR=str(D/'tmp'),XDG_CACHE_HOME=str(D/'cache'),TORCH_HOME=str(D/'cache/torch'),
 CUDA_VISIBLE_DEVICES='',MUSA_VISIBLE_DEVICES='',MTHREADS_VISIBLE_DEVICES='')
cmd=[PY,'-B',str(D/'phase_generate_entry.py'),'--checkpoints_dir',str(B/'weights/ardy_ckpt'),
     '--out_dir',str(out),'--enc_mode','stacked','--duration','4','--diffusion_steps','10',
     '--jobs',json.dumps(jobs),'--summary',str(out/'summary.json')]
def limits():
 os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4]);resource.setrlimit(resource.RLIMIT_AS,(40*1024**3,40*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(1200,1205))
start=time.monotonic();peak=0;reason=None
with (out/'generation.log').open('x') as f:
 try:p=subprocess.Popen(cmd,cwd=D,env=env,preexec_fn=limits,stdout=f,stderr=subprocess.STDOUT)
 except subprocess.SubprocessError as error:
  (out/'run.json').write_text(json.dumps(dict(spawn_failed=True,error=str(error),scope=scope),indent=2)+'\n')
  raise
 print(json.dumps(dict(pid=p.pid,scope=scope)),flush=True)
 for tick in range(590):
  if p.poll() is not None:break
  try:
   status=Path(f'/proc/{p.pid}/status').read_text();rss=next(int(l.split()[1]) for l in status.splitlines() if l.startswith('VmRSS:'));peak=max(peak,rss)
  except (FileNotFoundError,StopIteration):rss=0
  if rss>24*1024**2:reason='RSS24GiB bound'
  elif time.monotonic()-start>285:reason='wall285s bound'
  if reason:
   status=Path(f'/proc/{p.pid}/status').read_text();uid=next(int(l.split()[1]) for l in status.splitlines() if l.startswith('Uid:'))
   exe=Path(f'/proc/{p.pid}/cmdline').read_bytes().split(b'\0')[0].decode()
   assert uid==os.getuid() and exe==cmd[0] and Path(f'/proc/{p.pid}/cwd').resolve()==D
   p.terminate()
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.kill()
   break
  time.sleep(.5)
 rc=p.wait(timeout=10)
record=dict(command=cmd,exit_code=rc,wall_s=time.monotonic()-start,peak_rss_MiB=peak/1024,stop_reason=reason,scope=scope,source_manifest_sha=sha(D/'generator-provenance.json'))
if (out/'summary.json').exists():
 record['summary_sha']=sha(out/'summary.json');record['generated_files']={p.name:sha(p) for p in out.iterdir() if p.suffix in ['.npz','.csv']}
(out/'run.json').write_text(json.dumps(record,indent=2)+'\n')
with (B/'logs'/T/'steps.md').open('a') as f:f.write('- generation exit='+str(rc)+'; wall='+str(record['wall_s'])+'; peakRSSMiB='+str(record['peak_rss_MiB'])+'; log='+str(out/'generation.log')+'\n')
print(json.dumps(record,indent=2));raise SystemExit(0 if rc==0 else 1)
