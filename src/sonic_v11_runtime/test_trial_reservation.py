"""Isolated launch guard branch tests; no simulator, production counts untouched."""
import hashlib
import json
from pathlib import Path
from reserve_cpu_trial import reserve

root = Path(__file__).resolve().parent
out = root/'out/trial-reservation-tests'
out.mkdir()
fixture = out/'20261006-093203-codex-6385a841'
fixture.mkdir()
(fixture/'out').mkdir()
script = fixture/'sonic_grasp.py'
script.write_text('pass\n')
scope = dict(task=fixture.name,wave=5,max_physical_script_launches=20,data_budget_GiB=2)
scope_path = fixture/'active_cpu_wave.json'
scope_path.write_text(json.dumps(scope))
checks = []
def check(label, condition):
    assert condition, label
    checks.append(label)
def reject(label, fn):
    try:
        fn()
    except AssertionError:
        checks.append(label)
    else:
        raise AssertionError('Missing rejection: '+label)
first = reserve(fixture,script,'w5_0')
check('first_launch_branch',first['launch']==1)
reject('duplicate_name_rejected',lambda:reserve(fixture,script,'w5_0'))
reject('wrong_wave_prefix_rejected',lambda:reserve(fixture,script,'w4_wrong'))
reject('path_escape_rejected',lambda:reserve(fixture,script,'../w5_escape'))
reject('wrong_source_rejected',lambda:reserve(fixture,fixture/'other.py','w5_wrongsource'))
(fixture/'out/w5_existing').mkdir()
reject('existing_output_rejected',lambda:reserve(fixture,script,'w5_existing'))
scope_path.write_text(json.dumps({**scope,'data_budget_GiB':0}))
reject('storage_budget_rejected',lambda:reserve(fixture,script,'w5_disk'))
scope_path.write_text(json.dumps(scope))
for i in range(1,20):
    r = reserve(fixture,script,'w5_'+str(i))
    assert r['launch']==i+1
reject('twenty_first_launch_rejected',lambda:reserve(fixture,script,'w5_20'))
lines = (fixture/'wave5-launches.jsonl').read_text().splitlines()
check('rejections_never_consume_launch_slots',len(lines)==20 and len({json.loads(x)['name'] for x in lines})==20)
check('fixture_stays_in_owned_test_directory',fixture.resolve().is_relative_to(out.resolve()))
result = dict(physical_steps=0,passed=True,checks=checks,sandbox=str(fixture),
              production_wave_counts_touched=False,
              source_sha=hashlib.sha256((root/'reserve_cpu_trial.py').read_bytes()).hexdigest())
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
