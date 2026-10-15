#!/usr/bin/env python3
"""W4b FK check: injected real-robot grip config vs the built-in close_hand recipe.

Read-only. Loads a completed baseline cell (default b25_12_04 in rep_base),
takes the ACTUAL arm pose at the first CLOSE frame, and compares three 7-joint
hand configs by FK: pads' world positions, thumb<->opponent pad separation
(must stay >5mm or grasp_geometry.contact_frame raises), and the contact_frame
'expected object centre' error vs the real cube centre.
"""
import csv,gzip,json,sys,warnings
import numpy as np,mujoco
from pathlib import Path
warnings.filterwarnings('ignore')

B=Path('/data/group4/20261008-221515-qoder-03c4673f/ws4_migrate')
SRC=Path(sys.argv[1]) if len(sys.argv)>1 else B/'rep_base/rep/out/b25_12_04'
sys.path.insert(0,str(SRC.parent.parent))
from grasp_geometry import contact_frame

m=mujoco.MjModel.from_xml_path(str(SRC/'scene.xml'));d=mujoco.MjData(m)
hands=np.arange(36,43);hj=m.actuator_trnid[hands,0];hq=m.jnt_qposadr[hj]
names=[m.joint(int(j)).name for j in hj]
print('CELL',SRC.name)
print('HAND_JOINTS',names)
print('HAND_RANGES',[[round(x,4) for x in r] for r in m.jnt_range[hj].tolist()])
padnames=['right_thumb_fingertip','right_index_fingertip','right_middle_fingertip']
pads=[m.geom(n).id for n in padnames]
cubeid=m.body('red_cube').id

tr=np.load(SRC/'trajectory.npz',allow_pickle=True)
ph=[str(p) for p in tr['phase']]
i0=ph.index('CLOSE');q=tr['qpos'][i0].copy();t=float(tr['time'][i0])
cube=None
with gzip.open(SRC/'telemetry.csv.gz','rt') as f:
 idx=None
 for ln in f:
  if ln.startswith('#'):
   if idx is None and ln[2:].startswith('time_s'):idx={k:i for i,k in enumerate(ln[2:].rstrip('\n').split(','))}
   continue
  row=ln.rstrip('\n').split(',')
  if idx is None:idx={k:i for i,k in enumerate(row)};continue
  if abs(float(row[idx['time_s']])-t)<1e-9:
   cube=np.array([float(row[idx['cube_x_m']]),float(row[idx['cube_y_m']]),float(row[idx['cube_z_m']])]);break
print('CLOSE_ENTRY frame=%d t=%.3fs cube_centre_m=%s (dist from table/whatever not needed)'%(i0,t,np.round(cube,5).tolist()))

res=json.loads((SRC/'result.json').read_text())
cfgs={
 'A_recipe_pinch':np.array([0.,-.60,-.88,1.40,.08,1.40,.08]),
 'B_real_mirror':np.array(json.loads((B/'grip_real_map.json').read_text())['grip_target_rad']),
 'C_ik_output':np.array(res['adaptive_hand']['last']['command_rad']),
}
poses={}
for k,qh in cfgs.items():
 ok=bool(((qh>=m.jnt_range[hj,0]).all() and (qh<=m.jnt_range[hj,1]).all()))
 d.qpos[:]=q;d.qpos[hq]=qh;mujoco.mj_forward(m,d)
 p={n:d.geom_xpos[g].copy() for n,g in zip(padnames,pads)}
 R=d.xmat[cubeid].reshape(3,3).copy()
 tm=float(np.linalg.norm(p['right_middle_fingertip']-p['right_thumb_fingertip']))
 ti=float(np.linalg.norm(p['right_index_fingertip']-p['right_thumb_fingertip']))
 im=float(np.linalg.norm(p['right_middle_fingertip']-p['right_index_fingertip']))
 pt=contact_frame(m,d,R,opponent=2)
 err=pt-cube
 poses[k]=dict(pads=p,pt=pt)
 pad2cube={n:float(np.linalg.norm(p[n]-cube)) for n in padnames}
 print('--- %s in_range=%s'%(k,ok))
 print('    q=%s'%np.round(qh,4).tolist())
 print('    pads_m: thumb=%s index=%s middle=%s'%tuple(np.round(p[n],5).tolist() for n in padnames))
 print('    pad_sep_mm: thumb-middle=%.2f thumb-index=%.2f index-middle=%.2f (contact_frame needs thumb-middle>=5mm)'%(tm*1e3,ti*1e3,im*1e3))
 print('    pad_to_cube_centre_mm: thumb=%.1f index=%.1f middle=%.1f'%tuple(pad2cube[n]*1e3 for n in padnames))
 print('    contact_frame_point_m=%s err_vs_cube_mm=%.2f'%(np.round(pt,5).tolist(),np.linalg.norm(err)*1e3))

print('=== A vs B pad displacement (same wrist pose, mm) ===')
for n in padnames:
 dv=(poses['B_real_mirror']['pads'][n]-poses['A_recipe_pinch']['pads'][n])*1e3
 print('    %s d=%s |d|=%.1f'%(n,np.round(dv,1).tolist(),np.linalg.norm(dv)))
dv=(poses['B_real_mirror']['pt']-poses['A_recipe_pinch']['pt'])*1e3
print('    contact_frame_point d=%s |d|=%.1f  (arm target shifts this much before CLOSE)'%(np.round(dv,1).tolist(),np.linalg.norm(dv)))
print('=== A vs C pad displacement (mm) ===')
for n in padnames:
 dv=(poses['C_ik_output']['pads'][n]-poses['A_recipe_pinch']['pads'][n])*1e3
 print('    %s d=%s |d|=%.1f'%(n,np.round(dv,1).tolist(),np.linalg.norm(dv)))
dv=(poses['C_ik_output']['pt']-poses['A_recipe_pinch']['pt'])*1e3
print('    contact_frame_point d=%s |d|=%.1f'%(np.round(dv,1).tolist(),np.linalg.norm(dv)))
print('=== B vs C pad displacement (mm) ===')
for n in padnames:
 dv=(poses['B_real_mirror']['pads'][n]-poses['C_ik_output']['pads'][n])*1e3
 print('    %s d=%s |d|=%.1f'%(n,np.round(dv,1).tolist(),np.linalg.norm(dv)))
