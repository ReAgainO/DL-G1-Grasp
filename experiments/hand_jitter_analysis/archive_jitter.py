"""Archive this finite controller milestone only; never close remaining Track4 work."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,sys,tarfile,resource
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
R=Path(__file__).resolve().parent;T=R.name;B=Path('/home/group4/group4_dasc7606c');W=B/'work'/T;L=B/'logs'/T;C=B/'claims'/T
SID='01a0e195-925b-7fa1-b43f-e6f9391253df';REPORT=B/'reports'/(T+'-report.md')
RULES='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.datetime.now().astimezone().isoformat()
env=os.environ.copy()
for k in ['JOURNAL','ANCHOR','GPU_BASE','JOURNAL_BASE','ISSUES_BASE']:env.pop(k,None)
env.update(JOURNAL_BASE=str(B),GPU_BASE=str(B),ISSUES_BASE=str(B),PYTHONDONTWRITEBYTECODE='1')
def new(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False)
def log(message):
    with (L/'steps.md').open('a') as f:f.write('\n- '+now()+' '+message+'\n')
def command(args,label):
    logfile=R/'logs'/('archive-'+label+'.log')
    if logfile.exists():
        for attempt in range(2,6):
            candidate=R/'logs'/('archive-'+label+'-attempt'+str(attempt)+'.log')
            if not candidate.exists():logfile=candidate;break
        else:raise RuntimeError('Too many retained attempts for '+label)
    p=subprocess.run(args,cwd=B,env=env,capture_output=True,timeout=120)
    with logfile.open('xb') as f:f.write(p.stdout+b'\nSTDERR\n'+p.stderr)
    assert p.returncode==0,(label,p.returncode,(p.stdout+p.stderr).decode(errors='replace')[-3000:])
    return p.stdout.decode(errors='replace')
def evidence():
    summary=json.loads((R/'analysis/summary.json').read_text())
    assert summary['physics_trial_count']==28 and summary['all_prefix_exact'] and summary['all_original_baselines_bitwise_exact']
    assert summary['improved_successful_source_cases']==7 and summary['valid_clip_videos']==4
    for wi in range(1,8):
        assert (R/'configs'/f'wave{wi}-done.json').exists()
        e=json.loads((R/'analysis'/f'wave{wi}-evaluation.json').read_text())
        assert len(e['rows'])==4
        for row in e['rows']:
            assert sha(R/'out'/row['id']/'result.json')==row['source_result_sha']
            assert sha(R/'out'/row['id']/'dense_trace.npz')==row['source_dense_sha']
    videos=json.loads((R/'configs/render25clip-done.json').read_text())['rows']
    assert len(videos)==4 and all(v['rc']==0 and v['replay']['decoded_frames']==475 and v['replay']['decode_verified'] for v in videos)
    for v in videos:assert sha(R/'out'/v['id']/'replay25clip/grasp-25fps.mp4')==v['replay']['video_sha']
    assert sha(R/'REPORT.md')==sha(REPORT)==sha(W/'REPORT.md')
    return summary
def idle():
    from launch_safe import active
    running=active();assert not running,('own heavy processes remain',running)
def ledger(label):
    lines=(B/'claims/journal.log').read_text().splitlines()
    own=[{'line':i+1,'raw_json':s} for i,s in enumerate(lines) if json.loads(s).get('task')==T]
    index=[s for s in (B/'claims/INDEX.md').read_text().splitlines() if s.startswith('| '+T+' |')]
    value={'captured':now(),'own_events':own,'index_own_rows':index,'shared_tail_not_committed':True}
    new(W/('own-ledger-'+label+'.json'),value);return value
def git(*args):
    p=subprocess.run(['git','-C',str(B),*args],capture_output=True,timeout=120)
    assert p.returncode==0,p.stderr.decode(errors='replace');return p.stdout
def indexmap(raw):
    result={}
    for row in raw.split(b'\0'):
        if row:
            metadata,path=row.split(b'\t',1);result[path.decode()]=metadata.decode()
    return result
def commit(label):
    assert not git('ls-files','--unmerged').strip()
    targets=[C/'card.txt',C/'rules_seen',C/'rules_seen_after',L/'steps.md',REPORT]+[p for p in W.rglob('*') if p.is_file()]
    if (C/'done.txt').exists():targets.append(C/'done.txt')
    paths=sorted({str(p.relative_to(B)) for p in targets})
    allowed=(f'claims/{T}/',f'logs/{T}/',f'work/{T}/')
    assert all(p.startswith(allowed) or p==f'reports/{T}-report.md' for p in paths)
    assert not git('diff','--cached','--name-only','--',*paths).strip(),'own staged edits must be inspected, never reset'
    before=git('ls-files','--stage','-z');previous=git('rev-parse','HEAD').decode().strip()
    backup=R/'git';backup.mkdir(exist_ok=True)
    indexpath=Path(git('rev-parse','--git-path','index').decode().strip())
    if not indexpath.is_absolute():indexpath=B/indexpath
    shutil.copy2(indexpath,backup/('index-'+label+'.backup'))
    with (backup/('index-'+label+'-before.bin')).open('xb') as f:f.write(before)
    git('add','-f','--',*paths)
    author='Codex hp '+SID;email='codex-'+SID+'@worker00039.invalid';genv=env.copy()
    for role in ['AUTHOR','COMMITTER']:genv['GIT_'+role+'_NAME']=author;genv['GIT_'+role+'_EMAIL']=email
    p=subprocess.run(['git','-C',str(B),'-c','user.name='+author,'-c','user.email='+email,'commit','--only','-m','Archive hand-jitter milestone '+T+' '+label,'--',*paths],env=genv,capture_output=True,timeout=120)
    with (R/'logs'/('archive-git-'+label+'.log')).open('xb') as f:f.write(p.stdout+p.stderr)
    assert p.returncode==0,p.stdout+p.stderr
    digest=git('rev-parse','HEAD').decode().strip();after=git('ls-files','--stage','-z')
    bm,am=indexmap(before),indexmap(after)
    assert {p:v for p,v in bm.items() if p not in paths}=={p:v for p,v in am.items() if p not in paths},'unrelated staged blobs changed; do not reset'
    changed=git('diff-tree','--no-commit-id','--name-only','-r',digest).decode().splitlines();assert changed and set(changed)<=set(paths)
    assert git('show','-s','--format=%ae',digest).decode().strip()==email
    assert not git('status','--porcelain','--',*paths).strip()
    assert hashlib.sha256(git('show',digest+':reports/'+T+'-report.md')).hexdigest()==sha(REPORT)
    receipt={'time':now(),'previous_head':previous,'commit':digest,'author_email':email,'explicit_paths':paths,'changed_paths':changed,
             'unrelated_staged_blobs_preserved':True,'report_sha':sha(REPORT),'no_push':True}
    new(R/('git-'+label+'.json'),receipt);return receipt
def prepare():
    assert not (R/'git-initial.json').exists(),'initial commit already happened; inspect checkpoint without repeating prepare'
    summary=evidence();idle();assert sha(B/'AGENTS.md')==RULES==(C/'rules_seen').read_text().split()[0]
    if (C/'rules_seen_after').exists():assert (C/'rules_seen_after').read_text().split()[0]==RULES
    else:
        with (C/'rules_seen_after').open('x') as f:f.write(RULES+'  '+str(B/'AGENTS.md')+'\n')
    tools=B/'work/20260930-0310-qoder-issuereg'
    issue='ISS-H1-WHOLEHAND-PHYSICS-ARMED-KILLS-R3-SUCCESSES'
    history=[json.loads(s) for s in (B/'claims/issues.jsonl').read_text().splitlines() if json.loads(s).get('issue')==issue]
    assert history
    state=history[-1]['state']
    if state!='CLOSED':
        body='Finite matched-input hand jitter diagnostics:28 physics trials,7 prior-success cases retain original v2 success with19.3-63.6% lower HOLD wrist translational component RMS;B051 failure retry passes but world RMS increases. Model/hand/weights/geometry/gates unchanged; rotational and tracking tradeoffs remain. This is not a new population success rate or fullTrack4/hardware/ARDY attribution. Report '+str(REPORT)+'. All failures, render budget stops and scheduling deviation retained.'
        previous=[h for h in history if h.get('reporter_task')==T and h.get('title')=='Matched whole-hand jitter control experiments']
        if previous:assert len(previous)==1 and previous[0]['body']==body,'inspect own existing note instead of duplicating'
        else:command(['bash',str(tools/'issue_append.sh'),issue,'note',state,'Matched whole-hand jitter control experiments',body,'--field','reporter_task='+T,'--field','evidence='+str(REPORT)],'issue-note')
        command(['bash',str(tools/'issue_view.sh')],'issue-view')
    command(['bash',str(tools/'issue_verify.sh')],'issue-verify')
    ledger('preclose');log('Finite28-trial evidence and4 clip videos verified. Rules-after recorded; prior issue remains open; explicit-path initial Git follows.')
    receipt=commit('initial');new(W/'git-initial.json',receipt)
    new(R/'archive-precheck.json',{'time':now(),'summary_sha':sha(R/'analysis/summary.json'),'report_sha':sha(REPORT),'rules_sha':RULES,'initial_commit':receipt['commit'],'runtime_stamp':summary['runtime_stamp']})
    shutil.copy2(R/'archive-precheck.json',W/'archive-precheck.json')
    print(json.dumps({'phase':'prepared','commit':receipt['commit']}))
def pack():
    evidence();idle();assert (R/'archive-precheck.json').exists()
    log('Preparing immutable preclose transfer snapshot. Large assets stay in /data; no peer files or credentials included.')
    files={}
    for sub in ['analysis','configs','out','logs','source-snapshots']:
        for p in (R/sub).rglob('*'):
            if p.is_file() and not p.is_symlink() and p.name!='launch.lock':files['evidence/'+str(p.relative_to(R))]=p
    for p in R.iterdir():
        if p.is_file() and p.suffix in ['.py','.md','.json']:files['evidence/'+p.name]=p
    for p in W.rglob('*'):
        if p.is_file() and not p.is_symlink():files['server-mirror/work/'+T+'/'+str(p.relative_to(W))]=p
    for p in C.iterdir():
        if p.is_file():files['server-mirror/claims/'+T+'/'+p.name]=p
    files['server-mirror/logs/'+T+'/steps.md']=L/'steps.md';files['server-mirror/reports/'+REPORT.name]=REPORT
    manifest={'created':now(),'scope':'immutable preclose snapshot, final closure receipts delivered separately','files':{name:{'sha256':sha(p),'bytes':p.stat().st_size} for name,p in files.items()}}
    new(R/'transfer-manifest.json',manifest)
    with tarfile.open(R/'hand-jitter-evidence.tar.gz','w:gz',compresslevel=2) as tf:
        for name,p in sorted(files.items()):tf.add(p,arcname=name,recursive=False)
        tf.add(R/'transfer-manifest.json',arcname='transfer-manifest.json',recursive=False)
    receipt={'time':now(),'archive_sha':sha(R/'hand-jitter-evidence.tar.gz'),'archive_bytes':(R/'hand-jitter-evidence.tar.gz').stat().st_size,'manifest_sha':sha(R/'transfer-manifest.json'),'file_count':len(files)}
    new(R/'transfer-receipt.json',receipt);log('Transfer snapshot packed '+json.dumps(receipt));print(json.dumps(receipt))
def close():
    summary=evidence();idle();assert sha(B/'AGENTS.md')==RULES==(C/'rules_seen_after').read_text().split()[0]
    local=json.loads((R/'local-delivery-verification.json').read_text());transfer=json.loads((R/'transfer-receipt.json').read_text())
    assert local['passed'] and local['archive_sha']==transfer['archive_sha'] and local['manifest_sha']==transfer['manifest_sha'] and local['checked_files']==transfer['file_count']
    assert not (C/'done.txt').exists() and not (R/'close-receipt.json').exists()
    assert not git('diff','--cached','--name-only','--',f'claims/{T}',f'work/{T}',f'logs/{T}',f'reports/{T}-report.md').strip()
    assert shutil.disk_usage('/home').free>256*1024**2 and shutil.disk_usage(R).free>1024**3
    command(['bash',str(B/'work/journal/tools2/journal_verify.sh'),'--base',str(B)],'journal-preclose')
    note='Finite28-trial jitter milestone archived locally/server:7 prior successes retained original v2 gates,19.3-63.6% less HOLD wrist translational RMS; B051 retry passes with residual tradeoffs;4 verified25fps19s true-state clips. All28 outcomes and errors retained;remaining rotation/approach/fullTrack4 work not closed. NoGPU/nopeerfiles/no push.'
    output=command(['bash',str(B/'work/p0lock/close_ledger.sh'),T,'-',note,'done'],'close-ledger')
    verify=command(['bash',str(B/'work/journal/tools2/journal_verify.sh'),'--base',str(B)],'journal-postclose')
    snapshot=ledger('postclose');assert len(snapshot['index_own_rows'])==1 and '| done |' in snapshot['index_own_rows'][0]
    receipt={'time':now(),'close_output':output,'journal_verify':verify,'own_index_row':snapshot['index_own_rows'][0],
             'done_sha':sha(C/'done.txt'),'local_delivery_verified':True,'report_sha':sha(REPORT),'runtime_stamp':summary['runtime_stamp'],
             'scope':'this finite hand-jitter milestone only;remainingTrack4 issues remain open','no_push':True}
    new(R/'close-receipt.json',receipt);shutil.copy2(R/'close-receipt.json',W/'close-receipt.json')
    shutil.copy2(R/'local-delivery-verification.json',W/'local-delivery-verification.json');shutil.copy2(R/'transfer-receipt.json',W/'transfer-receipt.json')
    log('Finite milestone closed after both-location evidence verification. '+json.dumps({k:receipt[k] for k in ['time','own_index_row','done_sha','scope']}))
    final=commit('final');print(json.dumps({'phase':'closed','commit':final['commit'],'report_sha':sha(REPORT)}))
if __name__=='__main__':
    assert T=='20261009-170228-codex-fcd727b9'
    {'prepare':prepare,'pack':pack,'close':close}[sys.argv[1]]()
