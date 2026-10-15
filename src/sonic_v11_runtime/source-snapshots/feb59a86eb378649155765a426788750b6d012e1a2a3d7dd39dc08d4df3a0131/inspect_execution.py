"""Bounded, read-only compact view of actual execution and source lineage."""
import json
import sys
from pathlib import Path
from wave4_records import sha

root = Path(__file__).resolve().parent
assert 1 <= len(sys.argv[1:]) <= 20
for name in sys.argv[1:]:
    assert Path(name).name == name
    folder = root/'out'/name
    path = folder/'result.json'
    if not path.exists():
        print(json.dumps(dict(name=name,result_pending=True)))
        continue
    assert path.stat().st_size < 512*1024
    result = json.loads(path.read_text())
    stamp = result['runtime_stamp']
    for key,file in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:
        assert sha(folder/file) == stamp['model_sha'][key]
    main = root/'source-snapshots'/stamp['scene_generator_sha']/'sonic_grasp.py'
    assert main.is_file() and sha(main) == stamp['scene_generator_sha']
    for key in ['neutral_pose','execution_monitor']:
        saved = root/'source-snapshots'/stamp['library_sha'][key]/(key+'.py')
        assert saved.is_file() and sha(saved) == stamp['library_sha'][key]
    audit = result['execution_audit']
    assert audit['physics_samples'] == result['balance_audit_summary']['physics_steps']
    assert not result['body_action_override'] and not audit['state_mutations'] and not audit['control_mutations']
    phases = {phase:dict(max_arm_speed_rad_s=max(row['actual_velocity_max_rad_s'][22:29]),
                         peak_arm_joint=row['peak_arm_joint'],peak_arm_time_s=row['peak_arm_time_s'])
              for phase,row in audit['phases'].items()}
    print(json.dumps(dict(name=name,version=stamp['mujoco_version'],source_sha=stamp['scene_generator_sha'],
        result_sha=sha(path),trajectory_sha=sha(folder/'trajectory.npz'),success=result['success'],
        gates=result['gates'],fail_reason=result['fail_reason'],
        hold_min_mm=result['hold_min_lift_m']*1000,slip_mm=result['hold_slip_m']*1000,
        table_contact_max_N=result['balance_audit_summary']['robot_table_all_max_normal_N'],
        neutral_shoulder_offset_rad=result['neutral_shoulder_offset_rad'],
        max_actual_arm_speed_rad_s=audit['maximum_actual_arm_speed_rad_s'],
        body_limit_overshoot_rad=audit['maximum_body_joint_limit_overshoot_rad'],
        actual_to_decoded_rms_rad=result['actual_to_decoded_motor_target_rms_rad'],
        phases=phases,wall_s=result['wall_s'],full_task_balance_validated=result['full_task_com_cop_validated']),indent=2))
