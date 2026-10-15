"""Bounded immutable inventory; legacy success is NOT table-return success."""
import json
from pathlib import Path
from wave4_records import sha

MODULES = {'sonic_v11','reference_filter','motion_input','grasp_geometry',
    'policy_reference','discrete_reference','adaptive_hand','contact_audit',
    'decoded_arm_filter','balance_audit','source_physics_core','task_plan',
    'table_placement','finger_control','setdown_plan'}

def collect(root):
    launches = [json.loads(line) for line in (root/'wave5-launches.jsonl').read_text().splitlines()]
    assert 1 <= len(launches) <= 20
    assert len({x['name'] for x in launches}) == len(launches)
    records=[]; missing=[]; snapshots=[]
    for launch in launches:
        name=launch['name']; path=root/'out'/name/'result.json'
        if not path.is_file(): missing.append(name); continue
        assert path.stat().st_size<512*1024
        r=json.loads(path.read_text()); stamp=r['runtime_stamp']
        assert {'mujoco_version','sys_executable','python_version','model_sha','scene_generator_sha','library_sha','dt'} <= stamp.keys()
        sources=[('sonic_grasp.py',stamp['scene_generator_sha'])]
        sources += [(k+'.py',v) for k,v in stamp['library_sha'].items() if k in MODULES]
        for filename,digest in sources:
            saved=root/'source-snapshots'/digest/filename
            if not saved.is_file() or sha(saved)!=digest:
                snapshots.append(dict(episode=name,file=filename,sha=digest))
        for k,filename in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:
            assert sha(path.with_name(filename))==stamp['model_sha'][k]
        audit=path.with_name('release-destination.json')
        destination=json.loads(audit.read_text()) if audit.exists() else None
        if destination:
            assert destination['runtime_stamp']['library_sha']['episode']==sha(path)
        table=bool(r['gates'].get('final_table_supported',destination and destination['final_table_supported']))
        keys=['success','gates','gate_definition_version','duration_s','wall_s','model_load_s',
            'policy_p95_ms','policy_median_ms','max_lift_m','hold_min_lift_m','hold_slip_m',
            'hold_min_contact_bodies','max_drift_m','min_up_z','fail_reason','base_fixture',
            'no_grip','pad_off','ardy_off','phase_clips_consumed','independent_finger_kp_gain',
            'grip_preload_mm','grip_face_half_mm','setdown_enabled','setdown_plan',
            'balance_audit_summary','contact_audit_summary','actual_arm_velocity_per_joint_max_rad_s',
            'actual_arm_limit_overshoot_per_joint_max_rad','actual_to_decoded_motor_target_rms_rad',
            'user_corrections','correction_definition','reference_filter','table_front_x_m']
        record={k:r.get(k) for k in keys}
        record.update(name=name,launch=launch['launch'],runtime_stamp=stamp,
            result_sha256=sha(path),trajectory_sha256=sha(path.with_name('trajectory.npz')),
            final_table_supported=table,final_destination_audit=destination,
            audited_table_return_success=bool(r['success'] and table),
            controlled_placing_validated=bool(r['gates'].get('controlled_placing',False)))
        records.append(record)
    return dict(results=records,launches=launches,missing_results=missing,
        source_snapshot_missing=snapshots,recorded_episodes=len(records),
        legacy_successes=sum(r['success'] for r in records),
        audited_table_return_successes=sum(r['audited_table_return_success'] for r in records),
        controlled_placing_successes=sum(r['controlled_placing_validated'] for r in records),
        mixed_search_trials_not_a_success_rate=True)

if __name__=='__main__':
    data=collect(Path(__file__).resolve().parent)
    for r in data['results']:
        print(json.dumps({k:r[k] for k in ['name','launch','success','audited_table_return_success',
            'controlled_placing_validated','hold_min_lift_m','hold_slip_m','wall_s','fail_reason']}))
    print(json.dumps({k:v for k,v in data.items() if k not in ['results','launches']}))
