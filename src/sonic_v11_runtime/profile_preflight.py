"""Validate actual converted NPZ/CSV/text metadata, with zero physical steps."""
import argparse
import json
from pathlib import Path
from motion_profile import MotionProfile, ROLES, sha
from motion_input import ArdyMotion

p = argparse.ArgumentParser()
p.add_argument('profile')
p.add_argument('output')
a = p.parse_args()
root = Path(__file__).resolve().parent
output = root/'out'/a.output
if Path(a.output).name != a.output or output.suffix != '.json' or output.exists():
    raise ValueError('New bounded output filename required')
profile = MotionProfile(root, a.profile)
converted = {}
names = None
for role in ROLES:
    entry = profile.entries[role]
    motion = ArdyMotion(entry['npz'], check_csv=entry['csv'])
    profile.validate_motion(role, motion)
    if names is None:
        names = motion.joint_names
    assert names == motion.joint_names and len(names) == 29
    converted[role] = motion.audit
result = dict(physical_steps=0, new_generation_jobs=0, profile=profile.audit(),
    converted=converted, module_sha256=sha(root/'motion_profile.py'),
    limits='Input parity/identity only; no realizability, tracking, grasp or full-chain generation latency validation')
with output.open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(physical_steps=0, roles=profile.audit()['roles'], output=str(output)), indent=2))
