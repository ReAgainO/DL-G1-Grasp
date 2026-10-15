"""Saved-HOLD zero-step finger target-region regression and branch tests."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
from adaptive_hand import AdaptiveHand

root=Path(__file__).resolve().parent;out=root/'out/grip-face-region-tests';out.mkdir()
episode=root/'out/w5_setdown_gain3_free327';r=json.loads((episode/'result.json').read_text())
assert r['runtime_stamp']['mujoco_version']==mujoco.__version__
z=np.load(episode/'trajectory.npz',allow_pickle=False)
m=mujoco.MjModel.from_xml_path(str(episode/'scene.xml'));d=mujoco.MjData(m)
i=np.flatnonzero(z['phase']=='HOLD')[-1];d.qpos[:]=z['qpos'][i];d.qvel[:]=z['qvel'][i];mujoco.mj_forward(m,d)
cube=m.body('red_cube').id
args=[d,d.xpos[cube].copy(),d.xmat[cube].reshape(3,3).copy(),z['hand_reference'][i].copy()]
before=[d.qpos.copy(),d.qvel.copy(),d.ctrl.copy(),d.qfrc_applied.copy(),d.xfrc_applied.copy()]
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
old_sha=r['runtime_stamp']['library_sha']['adaptive_hand'];old_path=root/'source-snapshots'/old_sha/'adaptive_hand.py'
assert sha(old_path)==old_sha
spec=importlib.util.spec_from_file_location('prior_adaptive_face',old_path);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
baseline=old.AdaptiveHand(m,2);prior=baseline.solve(*args)
default=AdaptiveHand(m,2);current=default.solve(*args)
checks=[]
def check(label,condition):
    assert condition,label
    checks.append(label)
check('default_commands_bitwise_equal_old_source',np.array_equal(prior,current))
check('default_targets_bitwise_equal_old_source',baseline.last==default.last)
for half in [.006,.010,.015]:
    solver=AdaptiveHand(m,2,.0005,half);command=solver.solve(*args)
    targets=np.asarray(solver.last['target_points_m']);local=(targets-d.xpos[cube])@d.xmat[cube].reshape(3,3)
    axis=solver.last['opposing_cube_axis'];tangent=[j for j in range(3) if j!=axis]
    check(f'tangential_region_{half}',abs(local[:,tangent]).max()<=half+1e-12)
    check(f'normal_preload_unchanged_{half}',np.allclose(abs(local[:,axis]),.027,atol=1e-12))
    check(f'finite_in_limit_{half}',np.isfinite(command).all() and (command>=solver.lo).all() and (command<=solver.hi).all())
    check(f'inactive_index_unchanged_{half}',np.array_equal(command[3:5],args[-1][3:5]))
    if half==.010:check('ten_mm_region_changes_finger_goal',not np.array_equal(command,current))
for invalid in [.0059,.0151,np.nan,np.inf]:
    rejected=False
    try:AdaptiveHand(m,2,.0005,invalid)
    except ValueError:rejected=True
    check('reject_invalid_'+str(invalid),rejected)
check('observer_does_not_change_actual_state_control_forces',all(np.array_equal(a,b) for a,b in zip(before,[d.qpos,d.qvel,d.ctrl,d.qfrc_applied,d.xfrc_applied])))
answer=dict(runtime_stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,
    dt=.002,model_sha=r['runtime_stamp']['model_sha'],scene_generator_sha=sha(__file__),
    library_sha={'adaptive_hand':sha(root/'adaptive_hand.py'),'prior_adaptive_hand':old_sha,'episode':sha(episode/'result.json')}),
    physical_steps=0,passed=True,checks=checks,
    limitation='Finger target-region tests only; not actual contact margin or physical grasp/placing success.')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
