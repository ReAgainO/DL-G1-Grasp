"""Append factual fifth-wave errata/progress; no completion or shared edits."""
import datetime
import json
import os
import subprocess
from pathlib import Path

B=Path('/home/group4/group4_dasc7606c')
T='20261006-093203-codex-6385a841'
D=Path('/data/group4')/T;L=B/'logs'/T
marker=L/'wave5-first-free-grasp-note.json'
assert not marker.exists()
names=['w5_fingergain3_free327','w5_fingergain3_repeat327','w5_fingergain3_free314']
results=[json.loads((D/'out'/name/'result.json').read_text()) for name in names]
assert all(r['success'] and not r['base_fixture'] for r in results)
destinations={name:json.loads((D/'out'/name/'release-destination.json').read_text()) for name in [names[0],names[2]]}
assert destinations[names[0]]['final_table_supported']
assert destinations[names[2]]['final_floor_supported'] and not destinations[names[2]]['final_table_supported']
now=datetime.datetime.now().astimezone().isoformat()
text=f'''\n## [WAVE5 FREE GRASP / RELEASE ERRATUM] {now}
-Independent finger KP x3 / KD sqrt3 in CLOSE/LIFT/HOLD, thumb+middle only, original passive physics and factory actuator limits unchanged. Default PD bitwise-equivalence and bounds:23 unit checks passed. Geometric preload17 checks passed; increasing preload to1.5mm physically failed, remains nondefault.
-MuJoCo3.2.7 free pelvis same config2/2 passes existingv3 gates: HOLD126.430mm/slip3.807mm, foot minimum348.956N, no HOLD robot-table/nonfoot-floor/cube nonpad load. Peak actual wrist velocity and initial wrist/table interference remain; not real robot safety or full-task COM/COP evidence.
-MuJoCo3.14.0 free grasp HOLD136.712mm/slip4.113mm passes existingv3 gates, BUT release touches right_hip_yaw_link45.122..45.138s, then final cube is on FLOOR, not table. Original `final_supported` includes both floor/table. Do not call this complete table-return success; future gate must distinguish support geom. Historical raw results retained unchanged.
-3.2.7 final cube[.271581388,-.098810315,.774407879] has actual table_top support. 3.14.0 final cube[.365541395,-.0526920499,.0174539393] has floor support. Derived audit uses final20ms of ORIGINAL solver contacts, not rendered guesses.
-Same-source3.2.7 gain3 vs gain1 pair verified all runtime/model/source/weight hashes; first saved pose divergence33.282s; gain1 HOLD approximately0mm and peak14.383mm. This nominal/version-limited pair is not general causality.
-Earlier zero-step table-front counterfactual predicted removal of contacts in OLD saved poses. Actual front.24 runs still have initial right-wrist/table forces44.275N(3.2.7) /40.953N(3.14.0). Prediction did NOT prove collision avoidance in new dynamics.
-Failed diagnostics outside wrapper: system `python3 inspect_wave5.py` raised `ModuleNotFoundError: No module named numpy`; rerun using existing physics environment via run.sh. Remote `rg` read-only query failed `bash: line 1: rg: command not found`; used grep fallback. No installs.
-First table-placement test rejected all-body mass/inertia equality: changing fixed table geometry changes compiler-inferred static table mass42.52->42.07kg/inertia. Corrected test verifies robot/cube inertias and generalized qM bitwise unchanged, fixed table has no joints;15checks pass in newly named table-placement-tests-v2. Original failure retained.
-table_front_preflight scalar float(array) emitted NumPy DeprecationWarning; it did not alter a simulation. Future reuse should select scalar explicitly. Older local syntax read failed Windows gbk; explicit UTF-8 syntax check passed. No shared environment modification.
-Read-only official observation audit rejected a tempting generic6D rotation-convention change: policy deploy C++ explicitly row-wise-flattens first two matrix columns, matching existing encoder identity[1,0,0,1,0,0]. Export data transforms are a separate contract. No SONIC observation code changed.
-Prepared lift_progress.py monotone C2 scalar retimer16mathematical checks passed, NOT yet connected to physical pipeline, no performance claim or default change.
-Task remains ACTIVE. Current bounded wave<=20 launches,4CPU/AS16GiB/300s/90sim-s/cumulative task data2GiB. No GPU, KIMODO, public publish or real robot action.
'''
with (L/'steps.md').open('a') as f:f.write(text)
env=os.environ.copy()
for key in ['JOURNAL','ANCHOR','JOURNAL_BASE','GPU_BASE','ISSUES_BASE']:env.pop(key,None)
receipt=subprocess.run(['bash',str(B/'work/journal/tools2/journal_append.sh'),T,'note','-',
    '第五波首次自由底座抓取：MuJoCo3.2.7独立指PD增强同配置2/2，HOLD126.430mm/滑移3.807mm/脚支撑且HOLD无靠桌、最终确实落桌；3.14.0抓取保持136.712mm但释放碰髋并落地，旧final_supported混合桌/地不可称完整落桌成功。初始腕桌干扰未消除，不标完整Track4或实机完成；同源码指PD配对及两版阴性/ARDY消融继续，只写本任务。'],
    env=env,capture_output=True,text=True,timeout=60)
(L/'wave5-first-free-grasp-journal-receipt.txt').write_text(receipt.stdout+receipt.stderr)
assert receipt.returncode==0,(receipt.returncode,receipt.stdout,receipt.stderr)
with (L/'steps.md').open('a') as f:f.write(receipt.stdout+receipt.stderr)
answer=dict(time=now,task_active=True,recorded_names=names,journal_receipt=receipt.stdout+receipt.stderr,
    release_destination_erratum=True,raw_results_unmodified=True)
marker.write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
