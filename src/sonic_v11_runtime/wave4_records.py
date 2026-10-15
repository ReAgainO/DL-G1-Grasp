"""Bounded read-only evidence inventory for the fourth ARDY test wave."""
import hashlib
import json
from pathlib import Path

NAMES = [
    'w4_baseline314', 'w4_damping2', 'w4_damping3',
    'w4_contact_baseline327', 'w4_armature327', 'w4_passivefree327',
    'w4_armature314', 'w4_decoded_filter327', 'w4_decoded_light327',
    'w4_postgain2_327', 'w4_servo_hold327', 'w4_margin314',
    'w4_lift15_327', 'w4_lift15_repeat327', 'w4_lift15_padoff327',
    'w4_lift15_nogrip327', 'w4_lift15_fallback314',
    'w4_lift15_free327', 'w4_lift15_ardyoff327', 'w4_lift15_free314',
]

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()

def collect(root):
    records = []
    missing_results = []
    missing_sources = []
    modules = {
        'sonic_v11', 'reference_filter', 'motion_input', 'grasp_geometry',
        'policy_reference', 'discrete_reference', 'adaptive_hand',
        'contact_audit', 'decoded_arm_filter', 'balance_audit',
        'source_physics_core', 'task_plan',
    }
    for name in NAMES:
        path = root / 'out' / name / 'result.json'
        if not path.is_file():
            missing_results.append(name)
            continue
        assert path.stat().st_size < 512 * 1024
        result = json.loads(path.read_text())
        stamp = result['runtime_stamp']
        sources = [('sonic_grasp.py', stamp['scene_generator_sha'])]
        sources += [(key + '.py', value) for key, value in stamp['library_sha'].items() if key in modules]
        for filename, digest in sources:
            saved = root / 'source-snapshots' / digest / filename
            if not saved.is_file() or sha(saved) != digest:
                missing_sources.append(dict(episode=name, file=filename, sha=digest))
        keys = ['success', 'gates', 'legacy_success', 'gate_definition_version',
                'duration_s', 'wall_s', 'model_load_s', 'max_lift_m',
                'hold_min_lift_m', 'hold_slip_m', 'hold_min_contact_bodies',
                'max_drift_m', 'min_up_z', 'actual_to_decoded_motor_target_rms_rad',
                'actual_to_applied_motor_target_rms_rad', 'fail_reason',
                'phase_clips_consumed', 'reference_filter', 'ardy_off',
                'no_grip', 'pad_off', 'base_fixture', 'whole_body_balance_validated',
                'requested_postcapture_lift_height_m', 'sonic_armature',
                'passive_free_diagnostic', 'postcapture_arm_pd_gain_scale',
                'lift_only_right_arm_damping_scale', 'decoded_motor_filter',
                'actual_arm_velocity_per_joint_max_rad_s',
                'actual_arm_limit_overshoot_per_joint_max_rad',
                'balance_audit_summary', 'contact_audit_summary', 'policy_p95_ms']
        record = {key: result.get(key) for key in keys}
        record.update(name=name, result_sha256=sha(path), runtime_stamp=stamp,
                      trajectory_sha256=sha(path.with_name('trajectory.npz')),
                      final_phase=result['events'][-1]['phase'])
        records.append(record)
    return dict(results=records, missing_results=missing_results,
                source_snapshot_missing=missing_sources,
                recorded_episodes=len(records), successes=sum(r['success'] for r in records))

if __name__ == '__main__':
    data = collect(Path(__file__).resolve().parent)
    for r in data['results']:
        print(json.dumps(dict(name=r['name'], version=r['runtime_stamp']['mujoco_version'],
              success=r['success'], gate_version=r['gate_definition_version'],
              lift_mm=round(r['max_lift_m']*1000, 3),
              hold_min_mm=round(r['hold_min_lift_m']*1000, 3),
              slip_mm=round(r['hold_slip_m']*1000, 3),
              hold_min_pads=r['hold_min_contact_bodies'],
              final_phase=r['final_phase'], fail=r['fail_reason'],
              failed_gates=[k for k,v in r['gates'].items() if not v],
              reference=r['reference_filter'], balance=r['balance_audit_summary']),
              ensure_ascii=False))
    print(json.dumps({k:v for k,v in data.items() if k!='results'}, ensure_ascii=False))
