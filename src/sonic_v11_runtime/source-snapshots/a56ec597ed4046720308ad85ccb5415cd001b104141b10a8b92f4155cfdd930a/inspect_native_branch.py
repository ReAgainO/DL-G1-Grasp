"""Read finished native-branch rollouts without changing controls or artifacts."""
import json
import sys
from pathlib import Path
from wave4_records import sha

root=Path(__file__).resolve().parent
assert 1<=len(sys.argv[1:])<=20
for name in sys.argv[1:]:
    assert Path(name).name==name
    folder=root/'out'/name;path=folder/'result.json'
    if not path.exists():
        print(json.dumps(dict(name=name,result_pending=True)));continue
    assert path.stat().st_size<512*1024
    r=json.loads(path.read_text());stamp=r['runtime_stamp']
    for key,file in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:assert sha(folder/file)==stamp['model_sha'][key]
    for key in ['native_branch','execution_monitor','neutral_pose']:
        saved=root/'source-snapshots'/stamp['library_sha'][key]/(key+'.py')
        assert saved.exists() and sha(saved)==stamp['library_sha'][key]
    main=root/'source-snapshots'/stamp['scene_generator_sha']/'sonic_grasp.py'
    assert main.exists() and sha(main)==stamp['scene_generator_sha']
    assert r['post_clearance_native_branch_enabled'] and not r['body_action_override'] and not r['base_fixture']
    branch=r['post_clearance_native_branch']
    if branch:
        assert branch['selected_source_npz_sha256']==r['source']['source_npz_sha256']
        assert branch['actual_clearance_qualified_before_search'] and branch['actual_wrist_z_at_search_m']>=.9
        assert not branch['body_motor_target_override'] and not branch['object_state_writes']
    selected=branch['selected'] if branch else None
    print(json.dumps(dict(name=name,version=stamp['mujoco_version'],source_sha=stamp['scene_generator_sha'],
        result_sha=sha(path),trajectory_sha=sha(folder/'trajectory.npz'),success=r['success'],
        gates=r['gates'],stop_reason=r['fail_reason'],
        hold_min_mm=r['hold_min_lift_m']*1000 if r['hold_min_lift_m']!=-1 else None,
        slip_mm=r['hold_slip_m']*1000 if r['hold_slip_m']!=1e9 else None,
        table_peak_N=r['balance_audit_summary']['robot_table_all_max_normal_N'],
        actual_arm_speed_rad_s=r['execution_audit']['maximum_actual_arm_speed_rad_s'],
        actual_body_overshoot_rad=r['execution_audit']['maximum_body_joint_limit_overshoot_rad'],
        source_npz=r['source']['source_npz'],branch_selected=selected,
        branch_search_wall_s=branch.get('branch_search_wall_s') if branch else None,
        branch_time_s=branch.get('selected_time_s') if branch else None,events=r['events'],
        wall_s=r['wall_s'],duration_s=r['duration_s'],no_grip=r['no_grip']),indent=2))
