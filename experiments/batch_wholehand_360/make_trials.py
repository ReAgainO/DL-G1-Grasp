"""Freeze IDs and random draws before any counted experiments."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
import json,hashlib,sys,xml.etree.ElementTree as ET
import numpy as np
R=Path(__file__).resolve().parent
trials=[]
def add(id,group,xy,edge=.08,root=0,baseline=None,seed=None):
    row={'id':id,'group':group,'xy_m':list(map(float,xy)),'edge_m':float(edge),'mass_kg':.12,'root_x_m':float(root),
         'sampling_seed':seed,'source_baseline_trial':baseline,'no_grip':group=='NGR','wrist_servo':group!='NWS',
         'gravity_arm_scale':0. if group=='NGF' else 1.,'native_mesh':True,'time_scale':2.,'retract_raise':True}
    trials.append(row);return row
for i in range(100):add(f'A{i:03d}','A',[.35,-.18],seed=None)
rng=np.random.default_rng(20261009)
for i in range(100):add(f'B{i:03d}','B',rng.uniform([.33,-.20],[.37,-.16]),seed=20261009)
rng=np.random.default_rng(20261010)
for i in range(50):add(f'C{i:03d}','C',rng.uniform([.33,-.20],[.37,-.16]),rng.uniform(.07,.09),seed=20261010)
for i,row in enumerate([t for t in trials if t['group']=='C']):add(f'D{i:03d}','D',row['xy_m'],row['edge_m'],-.02,row['id'],20261010)
for group in ['NGR','NWS','NGF']:
    for i,row in enumerate([t for t in trials if t['group']=='B'][:20]):add(f'{group}{i:03d}',group,row['xy_m'],baseline=row['id'],seed=20261009)
assert len(trials)==360 and len({t['id'] for t in trials})==360
manifest={'version':'batch-v1','random_generator':'numpy.default_rng PCG64','numpy_version':np.__version__,
          'main_count':300,'ablation_count':60,'trials':trials,'representative_rule':'lowest numerical ID in each group and outcome; no borrowing across groups',
          'gate':'wholehand-v2-wristlocal-support','fixed_repeats':'A has no random state perturbation; determinism check, not generalization',
          'random_domain':{'xy_min_m':[.33,-.20],'xy_max_m':[.37,-.16],'edge_range_m':[.07,.09],'mass_kg':.12},
          'resource':{'cores':list(range(80,96)),'max_workers':8,'cores_per_worker':2,'job_AS_GiB':4,'per_command_timeout_s':600,
                      'batch_timeout_s':28800,'data_peak_GiB':20},
          'video':'all real recorded states from time0, including reach; 960x320 dual camera, 6.25fps real time',
          'planning_refusal_video':'real 10s safe standing; clearly NOT grasp execution',
          'sources_sha':{f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in
                         ['execute_batch.py','batch_plan.py','render_batch.py','batch_runner.py','wholehand_side.py','make_trials.py']}}
robot=ET.parse(R/'out/baseline_plan/robot.xml');meshdir=Path(robot.find('compiler').get('meshdir'))
asset_paths=sorted({str((meshdir/mesh.get('file')).resolve()) for mesh in robot.findall('asset/mesh') if mesh.get('file')})
assets={path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in asset_paths}
(R/'model-assets.json').write_text(json.dumps(assets,indent=2))
manifest['model_asset_manifest_sha']=hashlib.sha256((R/'model-assets.json').read_bytes()).hexdigest()
path=R/'manifest.json'
with path.open('x') as f:json.dump(manifest,f,indent=2)
(R/'configs').mkdir()
for row in trials:(R/'configs'/(row['id']+'.json')).write_text(json.dumps(row,indent=2))
(R/'manifest.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'  manifest.json\n')
print(json.dumps({'trials':len(trials),'manifest_sha':hashlib.sha256(path.read_bytes()).hexdigest()}))
