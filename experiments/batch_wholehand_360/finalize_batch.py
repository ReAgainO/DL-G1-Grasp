"""Own-task logged postprocessing, small mirrors and local-transfer bundle."""
import resource,os
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','LP_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import json,hashlib,subprocess,sys,datetime,shutil,tarfile,ast
R=Path(__file__).resolve().parent;T=R.name;B=Path('/home/group4/group4_dasc7606c');W=B/'work'/T
PY='/data/group4/20261004-205550-qoder-1280b420/env/bin/python'
RULES='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def note(s):
    with (B/'logs'/T/'steps.md').open('a') as f:f.write('\n- '+datetime.datetime.now().astimezone().isoformat()+' '+s+'\n')
def run(stage,args,bound=580):
    command=['timeout','--kill-after=5',str(bound),'taskset','-c','80,81',PY,'-B']+args
    note(stage+' START '+json.dumps(command));p=subprocess.run(command,cwd=R,env=os.environ.copy(),capture_output=True,text=True)
    log=R/'logs'/(stage+'.log')
    with log.open('x') as f:f.write(p.stdout+'\nSTDERR\n'+p.stderr)
    note(stage+' END rc='+str(p.returncode)+' log='+str(log)+' sha='+sha(log));print(p.stdout,p.stderr,flush=True)
    if p.returncode:raise SystemExit(p.returncode)
assert sha(B/'AGENTS.md')==RULES
action=sys.argv[1]
if action=='precheck':
    note('Postprocessing precheck, no new physics: current rules SHA '+RULES)
    for command in [['df','-h','/home','/data'],['free','-h']]:
        p=subprocess.run(command,capture_output=True,text=True,timeout=20)
        note(json.dumps(command)+' rc='+str(p.returncode)+'\n'+p.stdout)
        assert p.returncode==0
    for name in ['cpu','memory','io']:note('/proc/pressure/'+name+' '+Path('/proc/pressure',name).read_text())
    assert shutil.disk_usage('/home').free>256*1024**2
    assert shutil.disk_usage(R).free>1024**3
    print('Resource/rules precheck recorded; audit and video verification use separate bounded invocations.')
elif action=='audit-records':
    run('final-audit',[str(R/'audit_batch.py')])
elif action=='audit-records-again':
    note('Explicit second read-only audit: initial audit_batch.json/final-audit.log/v1 source retained; A legacy meshdir identity checked with exact path-only normalization and same resolved assets; no physics/gate change.')
    run('final-audit-02',[str(R/'audit_batch.py'),'--output','audit-final.json'])
elif action=='verify-videos':
    run('final-video-verification',[str(R/'verify_videos.py')])
elif action=='verify-video-again':
    assert len(sys.argv)==4,'provide new attempt ID and prior own attempt-report filename'
    note('Explicit new video-verification attempt only; previous logs retained; no physics rerun.')
    run('final-video-verification-'+sys.argv[2],[str(R/'verify_videos.py'),'--attempt',sys.argv[2],'--resume',sys.argv[3]])
elif action=='summarize':
    verified=json.loads((R/'video-verification.json').read_text())
    assert verified['checked_videos']==360 and not verified['failures'],'all independent video checks must pass first'
    assert verified['manifest_sha']==sha(R/'manifest.json') and verified['source_sha']==sha(R/'verify_videos.py')
    expected_ids={row['id'] for row in json.loads((R/'manifest.json').read_text())['trials']}
    assert len(verified['videos'])==360 and {row['id'] for row in verified['videos']}==expected_ids
    for row in verified['videos']:
        out=R/'out'/row['id']
        assert row['video_sha']==sha(out/'replay/grasp.mp4')
        assert row['source_result_sha']==sha(out/'result.json')
        assert row['source_trajectory_sha']==sha(out/'trajectory.npz')
    for path in R.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    for command in [['df','-h','/home','/data'],['free','-h']]:
        p=subprocess.run(command,capture_output=True,text=True);note(json.dumps(command)+' rc='+str(p.returncode)+'\n'+p.stdout)
    for name in ['cpu','memory','io']:note('/proc/pressure/'+name+' '+Path('/proc/pressure',name).read_text())
    note('Original pilot first-stage ValueError maximum AS limit retained; fixed before counted manifest. Strict NWS000 prechange audit first failed bitwise matching, readonly diagnostic showed maxreference2.4308766e-6rad/maxqpos3.3608463e-7; final audit retains all discrepancies as methodological warnings, not physical failure or unchanged-input causal evidence. No success-gate/physical source change after manifest freeze.')
    note('Local copy of frozen manifest SHA verified1757e01b98747133052fe06f97f44c485e043277fb276e0c9df2ab8b6621b3b3. Unsealed contact_frames/planning_refusal raw diagnostics not numeric citation sources. No GPU/no realrobot/others files modifications.')
    note('Owner local representative transfers before final audit: A000,B000,C000,D000,D011,NGR000,NWS000,NWS002,NGF000,B051,C046; replay.json ID and localMP4 SHA matched; all53.12s. HOLD images D000,D011,NGR000,NWS002,B051,C046 visually inspected. Final lowestID representative choices must be rechecked against complete summary, not interim availability.')
    run('final-summary',[str(R/'summarize_batch.py'),'--data-dir',str(R),'--executed-steps',str(B/'logs'/T/'steps.md'),
                        '--executed-command',f'timeout 180 /usr/bin/python3 -B {R}/server_prepare.py freeze',
                        '--executed-command',f'timeout 60 /usr/bin/python3 -B {R}/server_prepare.py launch',
                        '--executed-command',f'timeout --kill-after=5 580 taskset -c 80,81 {PY} -B {R}/audit_batch.py --output audit-final.json',
                        '--executed-command',f'timeout --kill-after=5 580 taskset -c 80,81 {PY} -B {R}/verify_videos.py'])
elif action=='mirror':
    assert shutil.disk_usage('/home').free>256*1024**2
    note('Two local JSON parsing attempts failed because read-only postprocess stdout was tool-truncated; observer compacted, no simulation/result/summary mutation. Original status reads retained in steps. All360 second decodes passed; A initial audit XML-path-only correction retained with original failure and exact v1 source.')
    names=[p.name for p in R.glob('*.py')]+[p.name for p in R.glob('*.ps1')]+[p.name for p in R.glob('*.md')]+['summary.json','audit-final.json','manifest.json','manifest.sha256','model-assets.json','video-verification.json']
    names += [name for name in ['audit_batch.json','audit-first-diagnostic.json','robot-identity-diagnostic.json','audit-early-pairs.json','B000-NWS000-diagnostic.json'] if (R/name).exists()]
    names=sorted(set(names))
    retained=sum(p.stat().st_size for p in W.rglob('*') if p.is_file() and p.parent!=W)
    assert retained+sum((R/name).stat().st_size for name in names)+(R/'REPORT.md').stat().st_size+2*1024**2<10*1024**2,'home mirror cap/reserve exceeded; keep extra diagnostics on data'
    for name in names:shutil.copy2(R/name,W/name)
    shutil.copy2(R/'REPORT.md',B/'reports'/(T+'-report.md'))
    note('Small source/report/result mirrors created in own work/reports; large pertrial/video artifacts remain own data.')
    with (W/'DATA-LOCATION.md').open('x') as f:f.write('# 原始数据落点\n\n'+str(R)+'\n\n完整360轮：out/<ID>，results-ledger.jsonl；原始轨迹/模型/视频在data，不挤占home。\n')
elif action=='pack':
    assert len(json.loads((R/'manifest.json').read_text())['trials'])==360
    targets=[R/name for name in ['REPORT.md','PROTOCOL.md','summary.json','audit-final.json','video-index.md','manifest.json','manifest.sha256',
                               'model-assets.json','video-verification.json','results-ledger.jsonl']]
    targets+=list(R.glob('*.py'))+list(R.glob('*.ps1'))+list(R.glob('*.md'))+[p for p in R.glob('*.json') if p.name!='transfer-receipt.json']
    targets+=list((R/'state').glob('*.json'))+list((R/'logs').glob('*.log'))
    shutil.copy2(B/'logs'/T/'steps.md',R/'steps-at-summary.md');targets.append(R/'steps-at-summary.md')
    for config in json.loads((R/'manifest.json').read_text())['trials']:
        out=R/'out'/config['id'];targets+=[out/'result.json',out/'episode_contract.json',out/'replay/replay.json',R/'state'/(config['id']+'.json'),
                                           R/'configs'/(config['id']+'.json')]
    targets=sorted(set(targets))
    with tarfile.open(R/'local-transfer.tar.gz','x:gz') as archive:
        for path in targets:archive.add(path,arcname=str(path.relative_to(R)),recursive=False)
    receipt={'bundle_sha':sha(R/'local-transfer.tar.gz'),'files':len(targets),'bytes':(R/'local-transfer.tar.gz').stat().st_size,
             'scope':'pre-close evidence snapshot; final ledger/Git/close receipts transferred separately, not a final closed archive',
             'source_root':str(R),'no_videos_in_bundle':'representative videos transferred separately with SHA checks'}
    (R/'transfer-receipt.json').write_text(json.dumps(receipt,indent=2));note('Local-transfer bundle '+json.dumps(receipt));print(json.dumps(receipt))
else:raise ValueError(action)
