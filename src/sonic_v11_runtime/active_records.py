"""Read-only current bounded CPU-wave status; all historical ledgers survive."""
import json
from pathlib import Path
from wave4_records import sha

root=Path(__file__).resolve().parent
scope=json.loads((root/'active_cpu_wave.json').read_text())
wave=scope['wave'];assert type(wave) is int and 5<=wave<=20
path=root/f'wave{wave}-launches.jsonl'
assert not path.exists() or path.stat().st_size<128*1024
launches=[json.loads(row) for row in path.read_text().splitlines()] if path.exists() else []
assert len(launches)<=20 and len({r['name'] for r in launches})==len(launches)
records=[]
for launch in launches:
    name=launch['name'];assert Path(name).name==name and name.startswith(f'w{wave}_')
    folder=root/'out'/name;result=folder/'result.json'
    if not result.exists():
        records.append(dict(name=name,result_pending=True,success=None));continue
    assert result.stat().st_size<512*1024
    r=json.loads(result.read_text());stamp=r['runtime_stamp']
    main=root/'source-snapshots'/stamp['scene_generator_sha']/'sonic_grasp.py'
    assert main.exists() and sha(main)==stamp['scene_generator_sha']
    for module in ['execution_monitor','neutral_pose','native_branch','branch_execution']:
        if module in stamp['library_sha']:
            snapshot=root/'source-snapshots'/stamp['library_sha'][module]/(module+'.py')
            assert snapshot.exists() and sha(snapshot)==stamp['library_sha'][module]
    for key,file in [('scene','scene.xml'),('robot','g1_free_grasp.xml')]:assert sha(folder/file)==stamp['model_sha'][key]
    assert not r['body_action_override'] and not r['base_fixture']
    records.append(dict(name=name,result_sha256=sha(result),version=stamp['mujoco_version'],
        success=r['success'],stop_reason=r['fail_reason'],failed_gates=[k for k,v in r['gates'].items() if not v],
        arm_speed_rad_s=r['execution_audit']['maximum_actual_arm_speed_rad_s'],
        body_limit_overshoot_rad=r['execution_audit']['maximum_body_joint_limit_overshoot_rad'],
        robot_table_max_N=r['balance_audit_summary']['robot_table_all_max_normal_N'],
        hold_min_mm=r['hold_min_lift_m']*1000 if r['hold_min_lift_m']!=-1 else None,
        slip_mm=r['hold_slip_m']*1000 if r['hold_slip_m']!=1e9 else None,
        input_npz=r['source']['source_npz'],input_npz_sha256=r['source']['source_npz_sha256'],
        motion_profile=r.get('motion_profile'),user_corrections=r['user_corrections'],
        no_grip=r['no_grip'],setdown_enabled=r['setdown_enabled'],
        source_sha256=stamp['scene_generator_sha'],branch_servo=r.get('post_clearance_branch_servo')))
print(json.dumps(dict(task=root.name,wave=wave,task_active=True,launch_count=len(launches),
    remaining_slots=20-len(launches),records=records,full_track4_complete=False,real_robot_ready=False,
    limits='Filesystem evidence snapshot, not proof of live-process status or a homogeneous success-rate estimate'),indent=2))
