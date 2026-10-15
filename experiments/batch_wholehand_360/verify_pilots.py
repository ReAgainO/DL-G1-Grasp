import os,resource
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
import json,sys,hashlib
from pathlib import Path
import numpy as np,mujoco
R=Path(__file__).resolve().parent
old=Path('/data/group4/20261009-003148-codex-363f6327/out/side80_native3')
new=R/'out/PBASE2'
with np.load(old/'trajectory.npz',allow_pickle=False) as a,np.load(new/'trajectory.npz',allow_pickle=False) as b:
    same={key:bool(np.array_equal(a[key],b[key])) for key in a.files}
assert all(same.values()),same
report={'baseline_all14_physical_arrays_bitwise_equal':same,'pilots':{}}
for name in ['PBASE2','PRAND2','PSIZE2','PBACK2']:
    out=R/'out'/name;result=json.loads((out/'result.json').read_text());contract=json.loads((out/'episode_contract.json').read_text())
    meta=json.loads((out/'replay/replay.json').read_text())
    assert result['success'] and meta['decode_verified'] and meta['duration_s']>52
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    assert meta['video_sha']==sha(out/'replay/grasp.mp4') and meta['source_trajectory_sha']==sha(out/'trajectory.npz')
    right=[g for g in contract['active_hand_geoms'] if g['body'].startswith('right_hand_') and g['contype']]
    assert len(right)==7
    report['pilots'][name]={'lift_m':result['max_lift_m'],'success':result['success'],'duration_s':meta['duration_s'],
                            'render_receipt':json.loads((R/'pilots'/(name+'-receipt.json')).read_text()),
                            'mujoco_version':mujoco.__version__,'video_sha':meta['video_sha']}
with (R/'pilots/verification.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
