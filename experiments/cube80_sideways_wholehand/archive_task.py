"""Archive only this claim's explicit files; preserve unrelated Git index blobs."""
from pathlib import Path
import json,hashlib,subprocess,sys,os,datetime,shutil

T='20261009-003148-codex-363f6327'
B=Path('/home/group4/group4_dasc7606c')
D=Path('/data/group4')/T
W=B/'work'/T
REPORT=B/'reports'/f'{T}-report.md'
SID='01a0e195-925b-7fa1-b43f-e6f9391253df'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.datetime.now().astimezone().isoformat()
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR']:env.pop(key,None)
env.update(JOURNAL_BASE=str(B),GPU_BASE=str(B),ISSUES_BASE=str(B),PYTHONDONTWRITEBYTECODE='1')

def command(args,label):
    p=subprocess.run(args,cwd=B,env=env,capture_output=True,timeout=120)
    target=D/'logs'/f'archive-{label}.log'
    with target.open('xb') as f:f.write(p.stdout+b'\nSTDERR\n'+p.stderr)
    if p.returncode:raise RuntimeError(f'{label} rc={p.returncode}: '+(p.stdout+p.stderr).decode(errors='replace')[-3000:])
    return p.stdout.decode(errors='replace')

def git(*args):
    p=subprocess.run(['git','-C',str(B),*args],capture_output=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    return p.stdout

def write_new(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2)

def own_ledger_snapshot(label):
    rows=[]
    allrows=(B/'claims/journal.log').read_text().splitlines()
    for i,line in enumerate(allrows,1):
        event=json.loads(line)
        if event.get('task')==T:rows.append({'journal_line':i,'raw_json':line})
    lines=[line for line in (B/'claims/INDEX.md').read_text().splitlines() if line.startswith('| '+T+' |')]
    value={'captured':now(),'master_journal_total_lines_at_read':len(allrows),'own_events':rows,'index_own_rows':lines,
           'scope':'own-row evidence only; master ledger shared tails not swept under this author'}
    write_new(W/f'own-ledger-{label}.json',value)
    return value

def commit_own(label):
    targets=[B/'claims'/T/'card.txt',B/'claims'/T/'rules_seen',B/'logs'/T/'steps.md',REPORT]
    targets+=list(W.rglob('*'))
    done=B/'claims'/T/'done.txt'
    if done.exists():targets.append(done)
    paths=sorted({str(p.relative_to(B)) for p in targets if p.is_file()})
    assert all(p.startswith(('claims/'+T+'/','logs/'+T+'/','work/'+T+'/')) or p=='reports/'+T+'-report.md' for p in paths)
    previous=git('rev-parse','HEAD').decode().strip()
    assert not git('ls-files','--unmerged').strip(),'repository has unresolved index conflicts; no commit'
    staged_before=git('ls-files','--stage','-z')
    gitdir=git('rev-parse','--git-path','index').decode().strip()
    ipath=Path(gitdir) if Path(gitdir).is_absolute() else B/gitdir
    backups=D/'git';backups.mkdir(exist_ok=True)
    shutil.copy2(ipath,backups/f'index-{label}.backup')
    (backups/f'staged-{label}-before.bin').write_bytes(staged_before)
    def mapping(raw):
        return {entry.split(b'\t',1)[1].decode():entry.split(b'\t',1)[0] for entry in raw.split(b'\0') if entry}
    before=mapping(staged_before)
    overlaps=[p for p in paths if p in before and git('diff','--cached','--name-only','--',p).strip()]
    if overlaps:raise RuntimeError('unexpected existing staged own-path overlap: '+repr(overlaps))
    git('add','-f','--',*paths)
    identity=['-c',f'user.name=Codex hp {SID}','-c',f'user.email=codex-{SID}@worker00039.invalid']
    commit_env=env.copy()
    for kind in ['AUTHOR','COMMITTER']:
        commit_env['GIT_'+kind+'_NAME']='Codex hp '+SID
        commit_env['GIT_'+kind+'_EMAIL']='codex-'+SID+'@worker00039.invalid'
    p=subprocess.run(['git','-C',str(B),*identity,'commit','--only','-m',f'Archive native whole-hand grasp {T} {label}','--',*paths],env=commit_env,capture_output=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')+p.stdout.decode(errors='replace'))
    current=git('rev-parse','HEAD').decode().strip()
    after=mapping(git('ls-files','--stage','-z'))
    unrelated_before={p:v for p,v in before.items() if p not in paths}
    unrelated_after={p:v for p,v in after.items() if p not in paths}
    assert unrelated_before==unrelated_after,'unrelated staged entries changed; investigate concurrent writer, do not reset'
    changed=git('diff-tree','--no-commit-id','--name-only','-r',current).decode().splitlines()
    assert changed and set(changed)<=set(paths)
    report_blob=git('show',current+':'+str(REPORT.relative_to(B)))
    assert hashlib.sha256(report_blob).hexdigest()==sha(REPORT)
    receipt={'timestamp':now(),'previous_head':previous,'commit':current,'explicit_paths':paths,'changed_paths':changed,
             'unrelated_staged_blobs_preserved':True,'report_blob_sha':sha(REPORT),'no_push':True}
    write_new(D/f'git-{label}.json',receipt)
    return receipt

def append_steps(body):
    with (B/'logs'/T/'steps.md').open('a') as f:f.write('\n'+body+'\n')

def prepare():
    expectation=json.loads((W/'archive-expectations.json').read_text())
    checked={}
    for path,expected in expectation['mirror'].items():
        p=B/path;assert sha(p)==expected,path
        checked[path]=expected
    for path,expected in expectation['data'].items():assert sha(path)==expected,path
    rules=(B/'claims'/T/'rules_seen').read_text().split()[0]
    assert sha(B/'AGENTS.md')==rules
    receipts=[]
    for p in (D/'logs').glob('*.receipt.json'):
        value=json.loads(p.read_text());receipts.append({'name':p.name,'returncode':value['returncode']})
    ps=subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True,check=True).stdout
    active=[line for line in ps.splitlines() if str(D/'execute_side.py') in line or str(D/'render_replay_clean.py') in line]
    assert not active,active
    evidence=str(REPORT)
    ia=B/'work/20260930-0310-qoder-issuereg/issue_append.sh'
    body=('New task-specific 80mm120g side-grasp, native7bones+physicalpalm/wrist, syntheticpadsOFF: lift108.574mm, wristlocal3.839mm, hold2.5s each-foot support; identical frozen repeat; matched open negative1.464mm/0hold. Not old35mm/H1b or v5/v6 success. Residual actual preclose contact35.389s peak10.045N, XY displacement0.411mm. Next: copy frozen execute_side.py into new claim, add dynamic preclose<0.1N gate and replan clearance; preserve lift/opposingload/foot gates; then3x3+-5mm fixed-base-placement pool. Cost60-120min. Evidence '+evidence+'; '+str(D/'native_audit2.json'))
    command(['bash',str(ia),'ISS-H1-WHOLEHAND-PHYSICS-ARMED-KILLS-R3-SUCCESSES','note','OPEN','New native-hand side-grasp milestone; original H1b geometry failure still open',body,'--field','reporter_task='+T,'--field','evidence='+evidence],'issue-wholehand')
    body2=('Native milestone uses near_s42 frame99/100 posture prior+reference IK/servo; not native fullbody time-varying ARDY. SONIC v1.1 decodes29body motors; independent7right-finger PD. No inference of ARDY necessity. Next: newclaim same frozen side geometry, compare native timevarying right-arm clip against constant/no-ARDYprior, leave leg/waist neutral initially; same physicssupport/slip/negative gates, do not mix pooledrates. Cost90-180min. Evidence '+evidence+'; '+str(D/'native_audit2.json'))
    command(['bash',str(ia),'ISS-GRASP-ARDY-ATTRIBUTION-BLOCKED','note','OPEN','Native grasp works with ARDY posture prior; fullbody and causal contribution still unverified',body2,'--field','reporter_task='+T,'--field','evidence='+evidence],'issue-ardy')
    command(['bash',str(B/'work/20260930-0310-qoder-issuereg/issue_view.sh')],'issue-view')
    issue_verify=command(['bash',str(B/'work/20260930-0310-qoder-issuereg/issue_verify.sh')],'issue-verify')
    append_steps('## [04] Final evidence / own archival\n'+
                 '- audit_native v1/v2 rc=0; before-CLOSE14/14 paired arrays exact, repeat14/14 exact, sampled preclose XY0.410827mm/XYZ1.330990mm. Runtime first contact35.389s; no collision-free claim.\n'+
                 '- clean render rc=0,238frames12.5fps/913652bytes,ffmpeg full decode; locally viewed HOLD image, same recorded states,0 integrations. Original remote video retained; local current preview replaced with clean version, original separately copied asgrasp_original.mp4.\n'+
                 '- remote rg unavailable: bash: line 1: rg: command not found; fallback grep used, no mutation from failed search.\n'+
                 '- independentLuna code review retained and reconciled with node raw audit. Official sources are scene/teleop references, not autonomous success policy.\n'+
                 '- own mirrors/data hashes all match pre-upload local expectations; own experiment/render processes absent. Receipts include failures and all retained.\n'+
                 '- existing issues supplemented with note only, not closed. Whole-track4/generalization not complete; no GPU reserved.\n'+
                 '- shared ledger contents intentionally not committed under this session author; own-row snapshots carry source line numbers and cutoff.\n'+
                 'Issue verification tail: '+issue_verify[-1800:])
    snapshot=own_ledger_snapshot('preclose')
    pre={'timestamp':now(),'mirror_hashes':checked,'data_hashes':expectation['data'],'local_artifacts_expected_hashes':expectation['local_artifacts'],
         'processes_absent':True,'receipts':receipts,'issue_verify_tail':issue_verify[-1800:],'own_ledger_cutoff':snapshot['master_journal_total_lines_at_read']}
    write_new(W/'archive-precheck.json',pre)
    commit=commit_own('initial')
    receipt={**pre,'initial_git':commit}
    write_new(D/'archive-receipt.json',receipt);shutil.copy2(D/'archive-receipt.json',W/'archive-receipt.json')
    append_steps('Initial own Git verified: '+json.dumps(commit)+'\nIncremental close receipts will archive next; no shared ledger sweep/no push.')
    print(json.dumps({'phase':'prepared','commit':commit['commit'],'mirror_files':len(checked),'unrelated_staged_preserved':True},indent=2))

def close():
    assert (D/'archive-receipt.json').is_file()
    own=[json.loads(line) for line in (B/'claims/journal.log').read_text().splitlines() if json.loads(line).get('task')==T]
    assert not any(x['event']=='done' for x in own),'already done: do not append another done event'
    summary='Native whole-hand single-scene milestone complete:80mm120g lift108.574mm wristlocal-slip3.839mm HOLD2.5s, deterministic repeat and no-grip negative1.464mm/0hold; SONIC29+fingerPD; syntheticpadsOFF/noobjectstateoverride. Progress/report/code/evidence dual archived; ARDY is posture prior, early contact and fullTrack4/generalization remain open; own CPU jobs exited.'
    closed=command(['bash',str(B/'work/p0lock/close_ledger.sh'),T,'-',summary,'done'],'close')
    verified=command(['bash',str(B/'work/journal/tools2/journal_verify.sh'),'--base',str(B)],'journal-verify')
    snapshot=own_ledger_snapshot('postclose')
    assert len(snapshot['index_own_rows'])==1 and '| done |' in snapshot['index_own_rows'][0]
    done=B/'claims'/T/'done.txt';assert done.is_file() and done.stat().st_size>0
    receipt={'timestamp':now(),'close_output':closed,'journal_verify_output':verified,'done_sha':sha(done),
             'own_index_row':snapshot['index_own_rows'][0],'journal_cutoff':snapshot['master_journal_total_lines_at_read'],
             'scope':'this finite native-hand milestone/report, NOT complete Track4','incremental_git_record':'git-final.json in own data/local archive'}
    write_new(D/'close-receipt.json',receipt);shutil.copy2(D/'close-receipt.json',W/'close-receipt.json')
    append_steps('## [05] Finite milestone closed\n'+json.dumps(receipt,indent=2)+'\nFinal own-path Git follows; all other paths/index blobs preserved, shared tail excluded from this author. No new event after final snapshot; no infinite archival recursion.')
    commit=commit_own('final')
    print(json.dumps({'phase':'closed','commit':commit['commit'],'done_sha':sha(done),'unrelated_staged_preserved':True,'journal_cutoff':snapshot['master_journal_total_lines_at_read']},indent=2))

if __name__=='__main__':
    assert Path(__file__).resolve().parent==D
    {'prepare':prepare,'close':close}[sys.argv[1]]()
