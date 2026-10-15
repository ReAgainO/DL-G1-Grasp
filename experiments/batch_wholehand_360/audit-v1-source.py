"""Read-only sampled-state audit, independent of scheduler and success flag."""
import os,resource
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from pathlib import Path
import json,hashlib,sys,argparse,xml.etree.ElementTree as ET
import numpy as np,mujoco
R=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=json.loads((R/'manifest.json').read_text());checks=[];pairs=[];template=None;fixed_same={};failures=[];warnings=[]
expected_common={'ardy_npz':'78eac68c405ceae93cb737b58022e83b5251d9d71def1eedb417caae0b73daff',
                 'sonic_module':'75815b28521b43d96c9abf6a1ac546763ac9c384eda6b8dd6389d7c15300fef2',
                 'sonic_models':{'model_encoder.onnx':'fb97de22819b2057b41459802128d91723d91a25f0ad73e7bfc41a9cf8365bae',
                                 'model_decoder.onnx':'34bae8570d4a4421a5391a5c2befd745d4a02d182ec539e5f9da44c091c67509',
                                 'observation_config.yaml':'4a67713b310932e50aca81f19188c8d76013148e98b15c8b5bbea995f12e59f0'}}
parser=argparse.ArgumentParser();parser.add_argument('--ids',nargs='*');parser.add_argument('--output',default='audit_batch.json');args=parser.parse_args()
configs=manifest['trials'] if not args.ids else [config for config in manifest['trials'] if config['id'] in args.ids]
assert len(configs)==(360 if not args.ids else len(set(args.ids)))
def inspect(config):
    name=config['id'];out=R/'out'/name;result=json.loads((out/'result.json').read_text())
    contract=json.loads((out/'episode_contract.json').read_text());stamp=result['runtime_stamp']
    assert contract['runtime_stamp']==stamp
    assert stamp['source_sha']==manifest['sources_sha']['execute_batch.py']
    assert stamp['planner_sha']==manifest['sources_sha']['wholehand_side.py']
    assert stamp['model_asset_manifest_sha']==manifest['model_asset_manifest_sha']==sha(R/'model-assets.json')
    assert stamp['model_sha']['robot']=='81d141121907c409db28bb09734007fd314193b687cf551feb2f47d2b12e0473'
    assert all(stamp['library_sha'][key]==value for key,value in expected_common.items()),'changed ARDY/SONIC dependency identity'
    assert stamp['scene_generator_sha']==manifest['sources_sha']['batch_plan.py']
    pdir=R/'out'/('plan_'+name);plan=json.loads((pdir/'plan.json').read_text())
    assert plan['trial_config']==config and stamp['library_sha']['plan']==sha(pdir/'plan.json')
    for key in ['robot','scene']:assert plan['runtime_stamp']['model_sha'][key]==sha(pdir/(key+'.xml'))
    if result['grasp_path_executed']:
        execution=json.loads((out/'execution_plan.json').read_text());assert execution['runtime_stamp']==stamp
        with np.load(out/'reference.npz',allow_pickle=False) as reference:assert json.loads(str(reference['runtime_stamp_json']))==stamp
        assert result['sonic']['models']==stamp['library_sha']['sonic_models']
    assert stamp['mujoco_version']==mujoco.__version__=='3.2.7'
    for key in ['robot','scene']:assert stamp['model_sha'][key]==sha(out/(key+'.xml'))
    with np.load(out/'trajectory.npz',allow_pickle=False) as tr:
        assert json.loads(str(tr['runtime_stamp_json']))==stamp
        assert np.isfinite(tr['qpos']).all() and np.isfinite(tr['qvel']).all()
        assert np.all(np.diff(tr['time'])>0)
        if 'pad_forces' in tr.files:assert np.max(abs(tr['pad_forces']))==0
    geoms=contract['active_hand_geoms']
    for side in ['left','right']:
        native=[g for g in geoms if g['body'].startswith(side+'_hand_') and g['contype'] and not g['name'].endswith('fingertip')]
        assert len(native)==7,(name,side,native)
        palm=[g for g in geoms if g['body']==side+'_wrist_yaw_link' and g['contype']]
        assert len(palm)>=1,(name,'palm_missing',side)
    for label in ['right_thumb_fingertip','right_index_fingertip','right_middle_fingertip']:
        g=next(g for g in geoms if g['name']==label);assert g['contype']==0 and g['conaffinity']==0
    assert contract['neq']==0 and contract['nmocap']==0 and contract['nq']==57 and contract['nu']==43
    assert contract['initial_qpos'][0]==config['root_x_m']
    assert contract['physical_gravity_m_s2']==[0.,0.,-9.81]
    scene=ET.parse(out/'scene.xml');cube=scene.find("worldbody/body[@name='red_cube']")
    pos=np.array(list(map(float,cube.get('pos').split())))
    assert np.allclose(pos,[*config['xy_m'],.725+config['edge_m']/2],atol=1e-15,rtol=0)
    assert np.allclose(list(map(float,cube.find('geom').get('size').split())),config['edge_m']/2)
    assert float(cube.find('geom').get('mass'))==config['mass_kg']
    row={'id':name,'classification':result['classification'],'native7_eachhand_and_palm_active':True,'no_sphere_contact':True,
         'runtime_hashes_verified':True,'stamp_coverage':'result, trajectory, episode_contract, planner XML/JSON, execution_plan and reference when grasp executed',
         'config_verified':True,'success':result['success'],'source_npz_sha':sha(out/'trajectory.npz'),
         'model_sha':stamp['model_sha'],'scene_generator_sha':stamp['scene_generator_sha'],'dt':stamp['dt']}
    if result['grasp_path_executed']:
        assert result['sonic']['decoded_target_adapter_used']==False
        assert result['sonic']['right_arm_gravity_feedforward_scale']==config['gravity_arm_scale']
        assert result['wrist_reference_servo']==config['wrist_servo']
        assert result['negative_control']==config['no_grip']
        assert result['no_cheats']['free_base'] and result['no_cheats']['free_object'] and result['no_cheats']['object_actuator_count']==0
        assert result['no_cheats']['xfrc_applied_max']==0 and result['no_cheats']['qfrc_applied_max']==0
        gate_from_recorded_counters=bool(result['reason']=='complete' and result['hold_support_steps']>=2000 and
                           result['hold_safe_steps']==result['hold_support_steps'] and result['max_wristlocal_slip_alllift_m']<=.01 and
                           result['max_joint_limit_violation_rad']<.002)
        assert gate_from_recorded_counters==result['success'];row['runtime_gate_consistency']=True
    return row
for config in configs:
    try:checks.append(inspect(config))
    except Exception as error:failures.append({'id':config['id'],'error':repr(error)})
    if config['group']=='A' and (R/'out'/config['id']/'trajectory.npz').exists():
        with np.load(R/'out'/config['id']/'trajectory.npz',allow_pickle=False) as tr:
            arrays={key:tr[key].copy() for key in tr.files if key!='runtime_stamp_json'}
        if template is None:template=arrays
        fixed_same[config['id']]=all(np.array_equal(value,template[key]) for key,value in arrays.items())
for config in configs:
    if config['group'] not in ['NGR','NWS','NGF']:continue
    source=config['source_baseline_trial'];target=config['id'];bp=R/'out'/source;ap=R/'out'/target
    try:
        br=json.loads((bp/'result.json').read_text());ar=json.loads((ap/'result.json').read_text())
        if not br['grasp_path_executed'] or not ar['grasp_path_executed']:
            pairs.append({'baseline':source,'ablation':target,'valid_physical_pair':False,'reason':'at least one planned path refused'});continue
        with np.load(bp/'reference.npz',allow_pickle=False) as rb,np.load(ap/'reference.npz',allow_pickle=False) as ra:
            reference_same={key:bool(np.array_equal(rb[key],ra[key])) for key in ['body','hand','wrist']}
            reference_delta={key:float(np.max(abs(rb[key]-ra[key]))) if rb[key].shape==ra[key].shape else None for key in reference_same}
        if not all(reference_same.values()):
            warnings.append({'baseline':source,'ablation':target,'kind':'precomputed_reference_not_bitwise_identical',
                             'max_abs_differences':reference_delta,
                             'interpretation':'independently replanned exogenous reference, not strict identical-input ablation; keep all physical results'})
        with np.load(bp/'trajectory.npz',allow_pickle=False) as b,np.load(ap/'trajectory.npz',allow_pickle=False) as a:
            bound=42. if config['group']=='NGR' else (34. if config['group']=='NWS' else .001)
            mask_b=b['time']<bound;mask_a=a['time']<bound
            same={key:bool(np.array_equal(b[key][mask_b],a[key][mask_a])) for key in ['qpos','qvel','ctrl','body_reference','hand_reference','cube_pos']}
            delta={key:float(np.max(abs(b[key][mask_b]-a[key][mask_a]))) for key in same}
            n=min(len(b['time']),len(a['time']));control_diff=float(np.max(abs(b['ctrl'][:n]-a['ctrl'][:n])))
            hand_diff=float(np.max(abs(b['hand_reference'][:n]-a['hand_reference'][:n])))
            if config['group']=='NGR':assert hand_diff>0
            if config['group']=='NWS':assert ar['max_servo_offset_rad']==0 and br['max_servo_offset_rad']>0 and control_diff>0
            if config['group']=='NGF':assert ar['sonic']['max_added_gravity_torque_Nm']==0 and br['sonic']['max_added_gravity_torque_Nm']>0 and control_diff>0
            strict=all(same.values()) if config['group']!='NGF' else None
            if strict is False:
                warnings.append({'baseline':source,'ablation':target,'kind':'prechange_not_bitwise_identical',
                                 'max_abs_differences':delta,'interpretation':'same scene samples but independently replanned inputs; not a strict identical-input ablation; descriptive current-version only'})
            pairs.append({'baseline':source,'ablation':target,'valid_physical_pair':True,'comparison_end_exclusive_s':bound,
                          'arrays_equal_before_change':same,'strict_prechange_bitwise_match':strict,'max_prechange_abs_differences':delta,
                          'prechange_scope':'NGF has no pretreatment time interval; initial-only comparison is not a pretreatment proof' if config['group']=='NGF' else 'sampled state/input prefix before switch',
                          'precomputed_reference_bitwise_match':reference_same,'max_precomputed_reference_abs_differences':reference_delta,
                          'strict_exogenous_reference_identity':all(reference_same.values()),
                          'max_control_difference_Nm':control_diff,'max_hand_reference_difference_rad':hand_diff,
                          'causal_scope':'same model and sampled scene, independently replanned references; strict input identity only if verified; NGF changes actuation from t0, NWS from34s, NGR from42s'})
    except Exception as error:failures.append({'id':target,'pair_error':repr(error)})
report={'mujoco_version':mujoco.__version__,'python_version':sys.version,'sys_executable':sys.executable,
        'manifest_sha':sha(R/'manifest.json'),'audit_source_sha':sha(__file__),'checked':len(checks),'failures':failures,'warnings':warnings,
        'trial_checks':checks,'fixed_A_arrays_bitwise_equal':fixed_same,'ablation_pairs':pairs,
        'evidence_limits':['trajectory is post-step sampled at20ms; success gate consistency uses original1ms runtime aggregate counters, not independent recomputation of every integration-step contact',
                           'object-state write prohibition is source audit, not an instrumentation hook',
                           'no second MuJoCo version and no native fullbody ARDY causal claim']}
stamps=[json.loads((R/'out'/row['id']/'result.json').read_text())['runtime_stamp'] for row in checks]
if stamps:
    report['runtime_stamp']={'mujoco_version':mujoco.__version__,'sys_executable':sys.executable,'python_version':sys.version,
                            'model_sha':{row['id']:row['model_sha'] for row in checks},
                            'scene_generator_sha':stamps[0]['scene_generator_sha'],
                            'library_sha':{'common':expected_common,'per_trial_plan':{row['id']:stamp['library_sha']['plan'] for row,stamp in zip(checks,stamps)}},
                            'dt':.001,'coverage':'each checked trial XML verified; provenance from original stamped results'}
assert Path(args.output).name==args.output
with (R/args.output).open('x') as f:json.dump(report,f,indent=2)
print(json.dumps({'checked':len(checks),'audit_failures':failures,'fixed_A_equal':sum(fixed_same.values()),'pair_count':len(pairs)}))
raise SystemExit(1 if failures else 0)
