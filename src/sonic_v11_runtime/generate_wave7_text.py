"""Fresh same-seed different-text CPU generation with cold and warm trace."""
import datetime
import hashlib
import json
import os
import resource
import subprocess
import time
from pathlib import Path
from wave4_records import sha

B=Path('/home/group4/group4_dasc7606c');T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;W=B/'work'/T;L=B/'logs'/T
PY='/data/group4/20261004-205543-qoder-f5a4a02a/env-gen/bin/python'
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
assert json.loads((D/'active_cpu_wave.json').read_text())['wave']==7
out=D/'out/w7-generated-text';assert not out.exists()
processes=subprocess.check_output(['ps','-eo','pid,args'],text=True).splitlines();assert len(processes)<20000
assert not any(str(D) in row and any(x in row for x in ['sonic_grasp.py','phase_generate_entry.py']) for row in processes)
actual=int(subprocess.check_output(['du','-sb',str(D)],text=True).split()[0]);assert actual+16*1024**2+320*1024**2<3*1024**3
assert sha(D/'generator_base.py')=='0d879f6c0ec458ed7f9731d7927bb7ea577dc7b424a7bc640549536f73b5818d'
provenance=json.loads((D/'generator-provenance.json').read_text())
assert 1<=len(provenance['source_files'])<=10000
for entry in provenance['source_files']:
    source=Path(entry['destination']);assert source.is_relative_to(D/'src/ardy_runtime') and sha(source)==entry['sha256']
old=json.loads((D/'out/generated_phases2/summary.json').read_text())
prompt=next(j['prompt'] for j in old['jobs'] if j['stem']=='reach_s43')
jobs=[dict(stem='w7_control_s43',seed=43,prompt=prompt),
    dict(stem='w7_upright_reach_s43',seed=43,prompt='A standing person slowly reaches down and forward with their right hand to grasp a small object on a table, keeping their torso upright and their left arm relaxed.')]
assert jobs[0]['prompt']!=jobs[1]['prompt'] and len(jobs)==2
scope=dict(time=datetime.datetime.now().astimezone().isoformat(),task=T,wave=7,
    jobs=len(jobs),frames_per_job=100,fps=25,cpu_cores=4,AS_GiB=40,RSS_GiB=24,
    timeout_s=285,physical_AS_GiB_unchanged=16,physical_steps=0,data_budget_GiB=3,
    purpose='Fresh cold process existing8B encoder+ARDY, same seed and genuinely different prompt; logs cold load and both warm jobs. No training, new weights, shared installation or GPU',
    generator_base_sha256=sha(D/'generator_base.py'),source_manifest_sha256=sha(D/'generator-provenance.json'),
    source_bytes_before=actual,interpretation='Text variants are input evidence, not semantic/physical task success; wall trace includes imports, load, jobs and output serialization')
out.mkdir();(out/'jobs.json').write_text(json.dumps(jobs,indent=2)+'\n');(W/'wave7-generation-scope.json').write_text(json.dumps(scope,indent=2)+'\n')
with (B/'claims'/T/'card.txt').open('a') as f:f.write('wave7_generation_scope='+json.dumps(scope)+'\n')
with (L/'steps.md').open('a') as f:f.write('\n## [WAVE7 FRESH TEXT GENERATION] '+json.dumps(scope)+'\n-2jobs x100frames, hardAS40/RSS24/4CPUs/285s only for previously verified8B CPU generator; physics stillAS16. No copied weights or new environment.\n')
ledger_env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:ledger_env.pop(key,None)
note=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
    '第七波新文本生成登记：仅两job各100帧25fps、相同seed43原文本/真正新文本；复用已验证8B CPU编码器及ARDY权重，不训练/下载/装环境/占GPU。沿用既有8B生成器专用4CPU/AS40GiB/RSS24GiB/285s例外，物理仿真仍AS16、20次上限及累计3GiB不变。输出D/out/w7-generated-text，记录冷加载、温job、总进程耗时；文本变化本身不等于语义或抓取成功。',
    '--field','generation_scope='+str(W/'wave7-generation-scope.json')],cwd=B,env=ledger_env,capture_output=True,text=True,timeout=60)
receipt=note.stdout+note.stderr;(L/'wave7-generation-receipt.txt').write_text(receipt)
assert note.returncode==0 and 'OK journal #' in receipt,(note.returncode,receipt)
with (L/'steps.md').open('a') as f:f.write(receipt+'\n')
env=os.environ.copy();env.update(PYTHONPATH=str(D/'src/ardy_runtime'),PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',
    OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
    HF_HOME=str(D/'cache'),HF_HUB_CACHE=str(D/'cache/hub'),TRANSFORMERS_OFFLINE='1',HF_HUB_OFFLINE='1',
    TMPDIR=str(D/'tmp'),XDG_CACHE_HOME=str(D/'cache'),TORCH_HOME=str(D/'cache/torch'),
    CUDA_VISIBLE_DEVICES='',MUSA_VISIBLE_DEVICES='',MTHREADS_VISIBLE_DEVICES='')
cmd=[PY,'-B',str(D/'phase_generate_entry.py'),'--checkpoints_dir',str(B/'weights/ardy_ckpt'),
    '--out_dir',str(out),'--enc_mode','stacked','--duration','4','--diffusion_steps','10',
    '--jobs',json.dumps(jobs),'--summary',str(out/'summary.json')]
def limits():
    os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4]);resource.setrlimit(resource.RLIMIT_AS,(40*1024**3,40*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(1200,1205))
start=time.perf_counter();peak=0;reason=None
with (out/'generation.log').open('x') as f:
    child=subprocess.Popen(cmd,cwd=D,env=env,preexec_fn=limits,stdout=f,stderr=subprocess.STDOUT)
    print(json.dumps(dict(pid=child.pid,scope=scope)),flush=True)
    for tick in range(590):
        if child.poll() is not None:break
        try:
            status=Path(f'/proc/{child.pid}/status').read_text();rss=next(int(line.split()[1]) for line in status.splitlines() if line.startswith('VmRSS:'));peak=max(peak,rss)
        except (FileNotFoundError,StopIteration):rss=0
        if rss>24*1024**2:reason='RSS24GiB limit'
        elif time.perf_counter()-start>285:reason='285s wall limit'
        if reason:
            status=Path(f'/proc/{child.pid}/status').read_text();uid=next(int(line.split()[1]) for line in status.splitlines() if line.startswith('Uid:'))
            command=Path(f'/proc/{child.pid}/cmdline').read_bytes().split(b'\0')
            assert uid==os.getuid() and command[0].decode()==PY and Path(f'/proc/{child.pid}/cwd').resolve()==D
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill()
            break
        time.sleep(.5)
    rc=child.wait(timeout=10)
record=dict(command=cmd,exit_code=rc,wall_process_s=time.perf_counter()-start,peak_rss_MiB=peak/1024,
    stop_reason=reason,scope=scope,gen_launcher_sha256=sha(__file__),generator_runtime_manifest_sha256=sha(D/'generator-provenance.json'))
if (out/'summary.json').exists():
    summary=json.loads((out/'summary.json').read_text());assert summary['skeleton_cls']=='G1Skeleton34' and summary['fps']==25
    assert len(summary['jobs'])==2 and all(job['num_frames']==100 for job in summary['jobs'])
    record.update(summary_sha256=sha(out/'summary.json'),cold_textencoder_load_s=summary['textencoder_load_s'],
        motion_model_load_s=summary['model_load_s'],warm_jobs_s=[job['wall_s'] for job in summary['jobs']],
        generated_files={path.name:sha(path) for path in out.iterdir() if path.suffix in {'.npz','.csv'}})
(out/'run.json').write_text(json.dumps(record,indent=2)+'\n')
with (L/'steps.md').open('a') as f:f.write('-fresh-text generator exit='+str(rc)+' wall_process_s='+str(record['wall_process_s'])+' peakRSSMiB='+str(record['peak_rss_MiB'])+' log='+str(out/'generation.log')+'. Import/load/serialize included, wall is not warm generation alone.\n')
print(json.dumps(record,indent=2));raise SystemExit(0 if rc==0 else 1)
