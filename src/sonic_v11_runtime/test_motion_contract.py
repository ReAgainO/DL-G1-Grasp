import json
from pathlib import Path
import numpy as np
from motion_input import ArdyMotion
root=Path(__file__).resolve().parent;folder=root/'out/motion-negative-tests';folder.mkdir();source=root/'src/original_motions/near_s42.npz'
with np.load(source,allow_pickle=False) as z:original={k:z[k].copy() for k in z.files}
tests=[]
def reject(label,fn):
 try:fn()
 except (ValueError,AssertionError):tests.append('reject_'+label)
 else:raise AssertionError(label+' unexpectedly accepted')
reject('fps_argument_20',lambda:ArdyMotion(source,source_fps=20))
for label in ['fps20','nan','nonrotation','reflection','wrong_shape','one_frame','missing_text']:
 z={k:v.copy() for k,v in original.items()}
 if label=='fps20':z['fps']=np.asarray(20)
 elif label=='nan':z['root_positions'][0,0]=np.nan
 elif label=='nonrotation':z['local_rot_mats'][0,0,0,0]+=1
 elif label=='reflection':z['local_rot_mats'][0,0,:,0]*=-1
 elif label=='wrong_shape':z['posed_joints']=z['posed_joints'][:,:33]
 elif label=='one_frame':
  for k in ['local_rot_mats','root_positions','posed_joints']:z[k]=z[k][:1]
 elif label=='missing_text':del z['text']
 path=folder/(label+'.npz');np.savez_compressed(path,**z);reject(label,lambda:ArdyMotion(path))
good=ArdyMotion(source);csv=root/'src/original_motions/near_s42.csv';ref=np.loadtxt(csv,delimiter=',')
for label in ['csv_nan','csv_swapped_joints','csv_bad_quaternion']:
 x=ref.copy()
 if label=='csv_nan':x[0,7]=np.nan
 elif label=='csv_swapped_joints':x[:,[7,8]]=x[:,[8,7]]
 else:x[:,3:7]*=2
 path=folder/(label+'.csv');np.savetxt(path,x,delimiter=',');reject(label,lambda:ArdyMotion(source,check_csv=path))
for label,clock in [('nan_clock',[np.nan]),('matrix_clock',[[0]]),('empty_clock',[]),('clock_bound',np.zeros(10001))]:reject(label,lambda:good.sample(clock))
q,v,r=good.sample(np.array([-1,0,good.times[-1]+1]));assert np.array_equal(q[0],good.qpos[0,7:]) and not v[[0,2]].any();tests.append('held_endpoints_have_zero_velocity')
assert np.allclose(np.linalg.norm(r,axis=1),1);tests.append('slerp_unit_quaternions')
result=dict(physical_steps=0,pass_count=len(tests),tests=tests);(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
