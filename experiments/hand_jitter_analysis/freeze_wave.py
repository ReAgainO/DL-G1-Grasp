"""Freeze finite <=4-trial waves without rewriting any executed physics code."""
from pathlib import Path
import datetime, hashlib, json, sys
R=Path(__file__).resolve().parent
B=Path('/home/group4/group4_dasc7606c')
OLD=Path('/data/group4/20261009-021611-codex-415484ce')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.datetime.now().astimezone().isoformat()
assert sha(B/'AGENTS.md')=='9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
wave=sys.argv[1]
spec=json.loads(Path(sys.argv[2]).read_text())
assert 1<=len(spec)<=4
hashes={n:sha(R/n) for n in ['execute_jitter.py','jitter_control.py','run_wave.py','wholehand_side.py','lib/sonic_v11.py']}
trials=[]
for c in spec:
    assert set(c)=={'id','source_episode','tau','damping','servo_gain','start'}
    assert c['id'].replace('_','').isalnum()
    c.update(source_hashes=hashes,frozen_source_reference_sha=sha(OLD/'out'/c['source_episode']/'reference.npz'))
    with (R/'configs'/(c['id']+'.json')).open('x') as f:json.dump(c,f,indent=2)
    trials.append(c)
design={'wave':wave,'frozen':now(),'trials':trials,'max_workers':4,'AS_GiB_per_worker':4,'no_gpu':True,
        'physics_gate':'unchanged wholehand-v2-wristlocal-support','freeze_source_sha':sha(__file__),
        'selection':'Require original success gate, exact pretreatment prefix, lower HOLD wrist RMS and arm velocity RMS. All failures retained.',
        'scope':'MuJoCo3.2.7 finite matched-input controller experiments; development or held-out status stated in report'}
with (R/'configs'/(wave+'-design.json')).open('x') as f:json.dump(design,f,indent=2)
with (B/'logs'/R.name/'steps.md').open('a') as f:f.write('\n- '+now()+' Frozen finite wave '+json.dumps(design)+'\n')
print(json.dumps({'wave':wave,'ids':[c['id'] for c in trials],'design_sha':sha(R/'configs'/(wave+'-design.json'))}),flush=True)
