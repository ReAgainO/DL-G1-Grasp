"""Create one new verified input manifest without generating new motion."""
import argparse
import json
from pathlib import Path
from motion_profile import MotionProfile, ROLES, sha

p = argparse.ArgumentParser()
p.add_argument('output')
a = p.parse_args()
root = Path(__file__).resolve().parent
output = root/'out'/a.output
if Path(a.output).name != a.output or output.suffix != '.json' or output.exists():
    raise ValueError('New JSON filename under out required')
summary = root/'out/generated_phases2/summary.json'
spec = dict(schema_version=1, generation_summary=str(summary.relative_to(root)),
    generation_summary_sha256=sha(summary), roles={})
for role, stem in zip(ROLES, ['reach_s43', 'lift_s42', 'hold_s42', 'release_s42']):
    source = summary.parent/stem
    spec['roles'][role] = dict(npz=str(source.with_suffix('.npz').relative_to(root)),
        csv=str(source.with_suffix('.csv').relative_to(root)),
        npz_sha256=sha(source.with_suffix('.npz')), csv_sha256=sha(source.with_suffix('.csv')),
        generation_job=stem)
with output.open('x') as stream:
    json.dump(spec, stream, indent=2)
    stream.write('\n')
profile = MotionProfile(root, str(output.relative_to(root)))
print(json.dumps(dict(profile=str(output), sha256=sha(output), roles=list(profile.entries),
    physical_steps=0, new_generation_jobs=0, human_corrections=0), indent=2))
