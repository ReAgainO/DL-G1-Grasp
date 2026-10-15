"""Readonly archived-trial analysis and new-task dependency preparation."""
import os
for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
import resource
resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import numpy as np
import mujoco

R = Path(__file__).resolve().parent
B = Path('/home/group4/group4_dasc7606c')
OLD = Path('/data/group4/20261009-021611-codex-415484ce')
RULES = '9e2c073c2ad7b602c4f378b2d8c7a653560375832c9825e5dc005ea65db9ca36'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert R.name == '20261009-170228-codex-fcd727b9'
assert sha(B / 'AGENTS.md') == RULES
assert mujoco.__version__ == '3.2.7'

def record(text):
    with (B / 'logs' / R.name / 'steps.md').open('a') as f:
        f.write('\n- ' + datetime.datetime.now().astimezone().isoformat() + ' ' + text + '\n')

def write_new(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2)

action = sys.argv[1]
if action == 'prepare':
    for notice in [B / 'NOTICE-disk-20261009.md', B / 'NOTICE-first-steps-20261003.md']:
        record('Entry notice ' + str(notice) + '\n' + notice.read_text())
    command = ['grep', '-nE', '抖动|jitter|振荡|oscillat|WHOLEHAND|wholehand', str(B / 'reports/open-issues.md')]
    p = subprocess.run(command, capture_output=True, text=True, timeout=20)
    record(f'Open issue lookup command={command} rc={p.returncode}\n{p.stdout}{p.stderr}')
    record('Initial remote rg lookup rc127: rg not installed on node; fallback grep used. Official start independently located at journal#2798.')
    sources = {}
    for name in ['wholehand_side.py', 'execute_batch.py', 'batch_plan.py', 'render_batch.py']:
        dst = R / ('execute_baseline.py' if name == 'execute_batch.py' else name)
        assert not dst.exists()
        shutil.copy2(OLD / name, dst)
        sources[name] = {'source': str(OLD / name), 'copy': str(dst), 'sha': sha(dst)}
        assert sha(OLD / name) == sha(dst)
    shutil.copytree(OLD / 'lib', R / 'lib', symlinks=True)
    (R / 'plandeps310').symlink_to(OLD / 'plandeps310', target_is_directory=True)
    for label in ['A000', 'B000', 'C000', 'D000', 'NWS000', 'NGF000', 'B051']:
        folder = R / 'source-snapshots' / label
        folder.mkdir()
        for name in ['reference.npz', 'execution_plan.json', 'result.json', 'episode_contract.json']:
            shutil.copy2(OLD / 'out' / label / name, folder / name)
        write_new(folder / 'source-identities.json', {name: sha(folder / name) for name in ['reference.npz', 'execution_plan.json', 'result.json', 'episode_contract.json']})
    sources['sonic_module'] = {'source': str(OLD / 'lib/sonic_v11.py'), 'copy': str(R / 'lib/sonic_v11.py'), 'sha': sha(R / 'lib/sonic_v11.py')}
    write_new(R / 'source-identities.json', sources)
    record('Prepared only own task sources; prior lib copied with symlinks preserved, prior env/deps/assets readonly. Frozen original reference snapshots retained for identical-input comparisons. ' + json.dumps(sources))
    print(json.dumps({'prepared': str(R), 'sources': sources}), flush=True)
elif action == 'analyze':
    rows = []
    for label in ['A000', 'B000', 'C000', 'D000', 'NWS000', 'NGF000', 'B051']:
        episode = OLD / 'out' / label
        result = json.loads((episode / 'result.json').read_text())
        trajectory = np.load(episode / 'trajectory.npz', allow_pickle=False)
        stamp = json.loads(str(trajectory['runtime_stamp_json']))
        assert stamp == result['runtime_stamp']
        assert stamp['mujoco_version'] == mujoco.__version__
        model = mujoco.MjModel.from_xml_path(str(episode / 'scene.xml'))
        jids = model.actuator_trnid[:, 0]
        qadr, vadr = model.jnt_qposadr[jids], model.jnt_dofadr[jids]
        times = trajectory['time']
        row = {'id': label, 'success': result['success'], 'source_stamp': stamp,
               'trajectory_sha': sha(episode / 'trajectory.npz'), 'source_result_sha': sha(episode / 'result.json'),
               'stored_dt_s': float(np.median(np.diff(times))), 'phases': {}}
        for name, low, high in [('AIR_APPROACH', 10, 30), ('LATE_APPROACH', 34, 42), ('CLOSE', 42, 45), ('LIFT', 46, 50.5), ('HOLD', 50.5, 53)]:
            choose = (times >= low) & (times < high)
            t = times[choose]
            q = trajectory['qpos'][choose][:, qadr]
            v = trajectory['qvel'][choose][:, vadr]
            ctrl = trajectory['ctrl'][choose]
            metric = {'samples': len(t)}
            for group, sl in [('right_arm', slice(22,29)), ('right_hand', slice(36,43))]:
                values = q[:, sl]
                # Linear detrending leaves oscillation but may also leave planned curvature.
                residual = values - np.c_[np.ones(len(t)), t-t[0]] @ np.linalg.lstsq(np.c_[np.ones(len(t)), t-t[0]], values, rcond=None)[0]
                spec = np.abs(np.fft.rfft(residual, axis=0)) ** 2
                freq = np.fft.rfftfreq(len(t), .02)
                band = (freq >= 1) & (freq <= 20)
                aggregate = spec[band].sum(axis=1)
                metric[group] = {'velocity_rms_rad_s': float(np.sqrt(np.mean(v[:,sl]**2))),
                                'velocity_peak_rad_s': float(abs(v[:,sl]).max()),
                                'angle_detrended_rms_deg': float(np.rad2deg(np.sqrt(np.mean(residual**2)))),
                                'dominant_1_20Hz': float(freq[band][np.argmax(aggregate)]),
                                'torque_step_rms_Nm': float(np.sqrt(np.mean(np.diff(ctrl[:,sl], axis=0)**2))),
                                'torque_saturation_fraction': float(np.mean((ctrl[:,sl] >= model.actuator_ctrlrange[sl,1]-1e-7) | (ctrl[:,sl] <= model.actuator_ctrlrange[sl,0]+1e-7)))}
            wrist = trajectory['wrist_pos'][choose]
            cube = trajectory['cube_pos'][choose]
            wr = wrist - np.c_[np.ones(len(t)),t-t[0]] @ np.linalg.lstsq(np.c_[np.ones(len(t)),t-t[0]],wrist,rcond=None)[0]
            metric['wrist_detrended_rms_mm'] = float(1000 * np.sqrt(np.mean(wr**2)))
            metric['wrist_range_mm'] = (1000*np.ptp(wrist,axis=0)).tolist()
            metric['cube_range_mm'] = (1000*np.ptp(cube,axis=0)).tolist()
            metric['decoded_arm_target_step_rms_deg'] = float(np.rad2deg(np.sqrt(np.mean(np.diff(trajectory['decoded_target'][choose][:,22:29],axis=0)**2))))
            metric['body_reference_arm_step_rms_deg'] = float(np.rad2deg(np.sqrt(np.mean(np.diff(trajectory['body_reference'][choose][:,22:29],axis=0)**2))))
            metric['finger_reference_step_rms_deg'] = float(np.rad2deg(np.sqrt(np.mean(np.diff(trajectory['hand_reference'][choose],axis=0)**2))))
            row['phases'][name] = metric
        rows.append(row)
        print(json.dumps({'id': label, 'HOLD': row['phases']['HOLD'], 'LATE_APPROACH': row['phases']['LATE_APPROACH']}), flush=True)
    output = {'analysis_kind': '20ms archived-sample descriptive diagnosis, no new dynamics', 'rows': rows,
              'runtime_stamp': {'mujoco_version': mujoco.__version__, 'python_version': sys.version, 'sys_executable': sys.executable,
                                'model_sha': {r['id']: r['source_stamp']['model_sha'] for r in rows},
                                'scene_generator_sha': sha(R / 'batch_plan.py'), 'library_sha': {r['id']: r['source_stamp']['library_sha'] for r in rows},
                                'dt': .001, 'analysis_source_sha': sha(__file__)},
              'limits': ['20ms sampling cannot resolve frequencies above25Hz; detrended approach residual includes planned curvature',
                         'Original representative videos sample6.25fps (160ms); not enough to reliably depict oscillations above3.125Hz',
                         'Frequency associations are not causal proof; higher-rate matched experiments follow']}
    write_new(R / 'analysis/archived-jitter.json', output)
    record('Readonly archived jitter analysis completed for7 fixed IDs, original state/identity checked. New stamped analysis: ' + str(R / 'analysis/archived-jitter.json'))
else:
    raise ValueError(action)
