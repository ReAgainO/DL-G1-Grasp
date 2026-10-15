"""Compare pre/post interface default arrays and new-clip consumption; read only."""
import argparse
import json
from pathlib import Path
import numpy as np
from motion_profile import sha

p = argparse.ArgumentParser()
p.add_argument('before')
p.add_argument('after')
p.add_argument('--expect-default-identical', action='store_true')
a = p.parse_args()
root = Path(__file__).resolve().parent
records = []
arrays = []
for name in [a.before, a.after]:
    if Path(name).name != name:
        raise ValueError('Bounded episode name required')
    folder = root/'out'/name
    r = json.loads((folder/'result.json').read_text())
    assert not r['body_action_override'] and not r['base_fixture']
    with np.load(folder/'trajectory.npz', allow_pickle=False) as z:
        assert len(z['qpos']) <= 2250
        arrays.append({k:z[k].copy() for k in ['qpos','qvel','body_reference','decoded_motor_target',
            'hand_reference','actuator_ctrl','time','phase']})
    records.append(r)
first, second = records
assert first['runtime_stamp']['model_sha'] == second['runtime_stamp']['model_sha']
assert first['runtime_stamp']['mujoco_version'] == second['runtime_stamp']['mujoco_version']
metrics = {}
for key in arrays[0]:
    lhs, rhs = arrays[0][key], arrays[1][key]
    row = dict(shape_before=list(lhs.shape), shape_after=list(rhs.shape))
    if lhs.shape == rhs.shape:
        row['identical'] = bool(np.array_equal(lhs,rhs))
        if lhs.dtype.kind not in 'US':
            row['max_abs_delta'] = float(np.max(abs(lhs-rhs)))
    if lhs.shape[1:] == rhs.shape[1:] and lhs.dtype.kind not in 'US':
        overlap = min(len(lhs),len(rhs))
        row['common_prefix_samples'] = overlap
        row['common_prefix_max_abs_delta'] = float(np.max(abs(lhs[:overlap]-rhs[:overlap])))
    metrics[key] = row
if a.expect_default_identical:
    assert first.get('motion_profile') is None and second.get('motion_profile') is None
    assert first['source']['source_npz_sha256'] == second['source']['source_npz_sha256']
    assert all(row.get('identical') for row in metrics.values()), metrics
else:
    assert first['source']['source_npz_sha256'] != second['source']['source_npz_sha256']
    profile = second['motion_profile']
    assert profile and set(profile['roles']) == {'reach','lift','hold','release'}
    assert second['source']['source_npz_sha256'] == profile['roles']['reach']['source_npz_sha256']
    assert second['runtime_stamp']['library_sha']['native_npz'] == second['source']['source_npz_sha256']
    assert second['ardy_arm_prior_consumed_by_sonic'] and not second['ardy_off']
    assert not second['endpoint_branch_seed'], 'Legacy endpoint must not masquerade as new input'
    assert metrics['body_reference']['common_prefix_max_abs_delta'] > 1e-6
    assert metrics['decoded_motor_target']['common_prefix_max_abs_delta'] > 1e-6
print(json.dumps(dict(physical_steps=0, before=a.before, after=a.after,
    before_result_sha256=sha(root/'out'/a.before/'result.json'),
    after_result_sha256=sha(root/'out'/a.after/'result.json'),
    mode='default input regression' if a.expect_default_identical else 'new input provenance and rollout difference',
    source_before=first['source']['source_npz_sha256'], source_after=second['source']['source_npz_sha256'],
    arrays=metrics, success_before=first['success'], success_after=second['success'],
    necessity_or_superiority_validated=False,
    limits='A changed input and rollout is not successful grasp, semantic generalization or evidence of ARDY necessity'),indent=2))
