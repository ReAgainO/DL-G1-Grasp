"""Bind newly generated reaches to prior phases with explicit per-job origins.

The merged JSON is a provenance index, NOT one fresh generation run. Original
summary/run files and their cold/warm timings remain separate and immutable.
"""
import copy
import json
from pathlib import Path
import numpy as np
from motion_profile import MotionProfile, ROLES, sha
from motion_input import ArdyMotion

root = Path(__file__).resolve().parent
old_path = root/'out/generated_phases2/summary.json'
new_path = root/'out/w7-generated-text/summary.json'
run_path = new_path.parent/'run.json'
out = root/'out/w7-source-binding'; assert not out.exists()
old = json.loads(old_path.read_text()); new = json.loads(new_path.read_text())
run = json.loads(run_path.read_text())
assert run['exit_code'] == 0 and run['summary_sha256'] == sha(new_path)
assert sha(old_path) == 'a1555c9380666c58b9d3084b6bf34dc52a0fcf5fabe55604befceb21fd98b003'
for summary in [old,new]:
    assert summary['fps']==25 and summary['skeleton_cls']=='G1Skeleton34'
    assert 1<=len(summary['jobs'])<=20
jobs=[]; sources={}
old_npz_sha={'lift_s42':'d9c93e72977af4853041063bccd87665f1ebb727b9c8a4c1f3003b01cb2fcdf5',
    'hold_s42':'4fc6a571e6661b9c345f5b1e669fbcd6d7713029e99d4b4c066dc5e0ad731096',
    'release_s42':'961dbba514c4ce6e3c31c30a44f7d9e98451477fe03df37fd616f1a0a2b2bc57'}
for summary,path,selected in [(new,new_path,['w7_control_s43','w7_upright_reach_s43']),
        (old,old_path,['lift_s42','hold_s42','release_s42'])]:
    for stem in selected:
        matches=[j for j in summary['jobs'] if j['stem']==stem];assert len(matches)==1
        job=copy.deepcopy(matches[0]);assert job['num_frames']==100
        origin=dict(path=str(path.relative_to(root)),sha256=sha(path),job_stem=stem)
        job['source_generation_summary']=origin
        source=path.parent/stem
        for ext in ['.npz','.csv']:
            assert source.with_suffix(ext).is_file()
            if path==new_path:assert run['generated_files'][source.with_suffix(ext).name]==sha(source.with_suffix(ext))
        if path==old_path:assert sha(source.with_suffix('.npz'))==old_npz_sha[stem]
        jobs.append(job);sources[stem]=source
assert jobs[0]['seed']==jobs[1]['seed']==43 and jobs[0]['prompt']!=jobs[1]['prompt']
assert len({j['stem'] for j in jobs})==5
merged=dict(schema_version=1,record_kind='verified_per_job_provenance_index_NOT_a_generation_run',
    fps=25,skeleton_cls='G1Skeleton34',jobs=jobs,
    source_summaries=[dict(path=str(p.relative_to(root)),sha256=sha(p)) for p in [old_path,new_path]],
    fresh_run=dict(path=str(run_path.relative_to(root)),sha256=sha(run_path)),
    interpretation='Two fresh reaches; three phases reused from original verified generation. No aggregate cold/warm timing is claimed for this index.')
out.mkdir();merged_path=out/'merged-source-summary.json'
merged_path.write_text(json.dumps(merged,indent=2)+'\n')
profiles={};motions={}
for label,reach in [('control','w7_control_s43'),('newtext','w7_upright_reach_s43')]:
    spec=dict(schema_version=1,generation_summary=str(merged_path.relative_to(root)),
        generation_summary_sha256=sha(merged_path),roles={},
        interpretation=merged['interpretation'])
    for role,stem in zip(ROLES,[reach,'lift_s42','hold_s42','release_s42']):
        src=sources[stem]
        spec['roles'][role]=dict(npz=str(src.with_suffix('.npz').relative_to(root)),
            csv=str(src.with_suffix('.csv').relative_to(root)),
            npz_sha256=sha(src.with_suffix('.npz')),csv_sha256=sha(src.with_suffix('.csv')),generation_job=stem)
    profile_path=out/(label+'-profile.json');profile_path.write_text(json.dumps(spec,indent=2)+'\n')
    profile=MotionProfile(root,str(profile_path.relative_to(root)))
    for role in ROLES:
        entry=profile.entries[role];motion=ArdyMotion(entry['npz'],check_csv=entry['csv'])
        profile.validate_motion(role,motion)
        if role=='reach':motions[label]=motion
    profiles[label]=profile.audit()
reference=ArdyMotion(old_path.parent/'reach_s43.npz',check_csv=old_path.parent/'reach_s43.csv')
control=motions['control'].qpos;modified=motions['newtext'].qpos
assert control.shape==modified.shape==reference.qpos.shape==(100,36)
delta=modified[:,29:36]-control[:,29:36]
assert abs(delta).max()>1e-6,'Different text did not change the actually consumed arm prior'
audit=dict(physical_steps=0,profiles=profiles,input_same_seed=43,
    original_control_prompt=motions['control'].text,new_prompt=motions['newtext'].text,
    text_equal=False,fresh_control_vs_original_same_seed=dict(
        qpos_exact=bool(np.array_equal(control,reference.qpos)),
        qpos_max_difference=float(abs(control-reference.qpos).max())),
    newtext_vs_control=dict(right_arm_max_delta_rad=float(abs(delta).max()),
        right_arm_rms_delta_rad=float(np.sqrt(np.mean(delta**2))),
        body_qpos_max_delta_rad=float(abs(modified[:,7:]-control[:,7:]).max())),
    merged_summary_sha256=sha(merged_path),fresh_run_sha256=sha(run_path),
    limitation='Input binding and generated arm change only. No semantics, physical success, unseen-object robustness, full-loop real-time or human correction claim. Controller uses neutral standing body plus ARDY arm seed/prior and simulator-state task scaffold; it does not execute all generated body poses.')
(out/'input-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(audit,indent=2))
