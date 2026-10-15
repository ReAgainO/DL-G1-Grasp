"""Zero-step regression of the bounded independent-finger preload parameter."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import mujoco
import numpy as np
import source_physics_core as core
from adaptive_hand import AdaptiveHand

root = Path(__file__).resolve().parent
out = root/'out/grip-preload-tests'
out.mkdir()
episode = root/'out/w5_front240_live327'
r = json.loads((episode/'result.json').read_text())
assert r['runtime_stamp']['mujoco_version'] == mujoco.__version__
z = np.load(episode/'trajectory.npz', allow_pickle=False)
m = mujoco.MjModel.from_xml_path(str(episode/'scene.xml'))
d = mujoco.MjData(m)
i = np.flatnonzero(z['phase']=='CLOSE')[-1]
d.qpos[:] = z['qpos'][i]
d.qvel[:] = z['qvel'][i]
mujoco.mj_forward(m, d)
cube = m.body('red_cube').id
before = [d.qpos.copy(), d.qvel.copy(), d.ctrl.copy(), d.qfrc_applied.copy(), d.xfrc_applied.copy()]
old_sha = r['runtime_stamp']['library_sha']['adaptive_hand']
old_path = root/'source-snapshots'/old_sha/'adaptive_hand.py'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(old_path) == old_sha
spec = importlib.util.spec_from_file_location('prior_adaptive_hand', old_path)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
seed = z['hand_reference'][i].copy()
old_solver = old.AdaptiveHand(m, 2)
new_default = AdaptiveHand(m, 2)
arguments = [d, d.xpos[cube].copy(), d.xmat[cube].reshape(3, 3).copy(), seed]
a = old_solver.solve(*arguments)
b = new_default.solve(*arguments)
checks = []
def check(label, condition):
    assert condition, label
    checks.append(label)
check('default_commands_bitwise_equal_prior_source', np.array_equal(a, b))
check('default_target_points_bitwise_equal_prior_source', old_solver.last == new_default.last)
for preload in [.00025, .0015, .0025]:
    solver = AdaptiveHand(m, 2, preload)
    command = solver.solve(*arguments)
    check(f'finite_in_limit_{preload}', np.isfinite(command).all() and (command>=solver.lo).all() and (command<=solver.hi).all())
    check(f'inactive_index_unchanged_{preload}', np.array_equal(command[3:5], seed[3:5]))
    local = (np.asarray(solver.last['target_points_m'])-d.xpos[cube])@d.xmat[cube].reshape(3, 3)
    axis = solver.last['opposing_cube_axis']
    check(f'physical_face_preload_exact_{preload}', np.allclose(abs(local[:, axis]), .0275-preload, atol=1e-12))
for invalid in [-.1, 0, .00251, np.nan, np.inf]:
    rejected = False
    try:
        AdaptiveHand(m, 2, invalid)
    except ValueError:
        rejected = True
    check(f'invalid_preload_rejected_{invalid}', rejected)
check('input_state_and_controls_unchanged', all(np.array_equal(a, b) for a, b in zip(before, [d.qpos, d.qvel, d.ctrl, d.qfrc_applied, d.xfrc_applied])))
stamp = dict(mujoco_version=mujoco.__version__, sys_executable=sys.executable, python_version=sys.version,
    dt=float(m.opt.timestep), model_sha=r['runtime_stamp']['model_sha'], scene_generator_sha=sha(__file__),
    library_sha={'adaptive_hand':sha(root/'adaptive_hand.py'), 'prior_adaptive_hand':old_sha,
        'episode':sha(episode/'result.json'), 'trajectory':sha(episode/'trajectory.npz')})
answer = dict(runtime_stamp=stamp, passed=True, physical_steps=0, checks=checks,
    limitations='FK and parameter branch tests only; preload is NOT a measured normal-force guarantee or grasp-success evidence.')
(out/'result.json').write_text(json.dumps(answer, indent=2)+'\n')
print(json.dumps(answer, indent=2))
