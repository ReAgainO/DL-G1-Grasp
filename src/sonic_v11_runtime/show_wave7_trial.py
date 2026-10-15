"""Small evidence view; file readiness is never asserted as process liveness."""
import json,sys
from pathlib import Path
from wave4_records import sha
root=Path(__file__).resolve().parent
assert 1<=len(sys.argv[1:])<=20
for name in sys.argv[1:]:
 assert Path(name).name==name and name.startswith('w7_') and len(name)<128
 path=root/'out'/name/'result.json'
 if not path.exists():print(json.dumps(dict(name=name,result_present=False,process_status='not inferred')));continue
 assert path.stat().st_size<512*1024;r=json.loads(path.read_text());branch=r.get('post_clearance_native_branch')
 answer=dict(name=name,result_present=True,result_sha256=sha(path),version=r['runtime_stamp']['mujoco_version'],
 source_sha256=r['runtime_stamp']['scene_generator_sha'],success=r['success'],fail_reason=r['fail_reason'],
 duration_s=r['duration_s'],wall_s=r['wall_s'],failed_gates=[k for k,v in r['gates'].items() if not v],
 hold_min_mm=r['hold_min_lift_m']*1000 if r['hold_min_lift_m']!=-1 else None,
 slip_mm=r['hold_slip_m']*1000 if r['hold_slip_m']!=1e9 else None,
 table_peak_N=r['balance_audit_summary']['robot_table_all_max_normal_N'],
 branch_face_alignment_enabled=r.get('branch_face_alignment_enabled'),
 branch_selected=branch['selected'] if branch else None,
 branch_live_search_time_s=branch['search_state']['time_s'] if branch and 'search_state' in branch else None,
 loop_latency=r.get('execution_cycle_latency',{}).get('complete_50Hz_cycles'),
 body_action_override=r['body_action_override'],base_fixture=r['base_fixture'],peak_external_force=r['peak_external_force'])
 print(json.dumps(answer,indent=2))
