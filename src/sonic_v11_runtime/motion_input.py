"""Native ARDY-G1 NPZ -> named MuJoCo qpos, with explicit clock and provenance.

The NumPy conversion mirrors the archived NVIDIA ARDY converter (Apache-2.0).
It uses local rotation matrices, not inferred angles from the animation skeleton.
Original inputs remain unchanged and optional CSV is only a parity check.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import mujoco,numpy as np
import sonic_v11 as s
ROOT=Path(__file__).resolve().parent
COORD=np.array([[0,1,0],[0,0,1],[1,0,0]],dtype=np.float32)

def convert(z,names,xml):
 tree=ET.parse(xml);root=tree.getroot()
 joints=root.find('worldbody').findall('.//joint')
 assert len(joints)==29,'Expected29 body hinges, no hand channels'
 defaults={x.get('class'):x.find('joint').get('axis') for x in root.findall('.//default')
           if x.get('class') and x.find('joint') is not None}
 parents={child:parent for parent in root.iter() for child in parent}
 frames=len(z['root_positions']);q=np.zeros((frames,36),np.float64)
 q[:,:3]=np.asarray(z['root_positions'],np.float32)@COORD
 matrices=np.asarray(z['local_rot_mats'],np.float32)
 rot=COORD.T@matrices[:,0]@COORD
 for i in range(frames):
  quat=np.zeros(4);mujoco.mju_mat2Quat(quat,np.asarray(rot[i],np.float64).reshape(-1));q[i,3:7]=quat
 joint_names=[]
 for j,joint in enumerate(joints):
  name=joint.get('name');idx=names.index(name.replace('_joint','_skel'));joint_names.append(name)
  axis=np.fromstring(joint.get('axis') or defaults[joint.get('class')],sep=' ')
  # Mirror vendor's positive canonical-axis selection; reject unsupported axes.
  assert axis.size==3 and np.count_nonzero(axis)==1 and np.max(axis)==1
  axis_ardy=np.argmax(COORD@axis)
  body=parents[joint]
  if body.get('quat'):
   offset=s.rotation(np.fromstring(body.get('quat'),sep=' '))
   offset=(COORD@offset@COORD.T).T.astype(np.float32)
  else:offset=np.eye(3,dtype=np.float32)
  local=offset@matrices[:,idx]
  dofs=np.stack([np.arctan2(local[:,2,1],local[:,2,2]),np.arctan2(local[:,0,2],local[:,0,0]),
                 np.arctan2(local[:,1,0],local[:,1,1])],axis=-1)
  q[:,7+j]=dofs[:,axis_ardy]
 return q,joint_names

class ArdyMotion:
 def __init__(self,npz_path,source_fps=25,check_csv=None):
  path=Path(npz_path)
  if path.stat().st_size>100*1024**2:raise ValueError('Input exceeds100MiB bounded contract')
  with np.load(path,allow_pickle=False) as z:
   for k in ['fps','text','local_rot_mats','root_positions','posed_joints']:
    if k not in z:raise ValueError('Missing native NPZ field '+k)
   fps=float(z['fps'])
   if fps!=25 or source_fps!=fps:raise ValueError('Native ARDY-G1 requires25fps; explicit fps mismatch')
   n=len(z['root_positions'])
   if not 2<=n<=2250:raise ValueError('Frame bound2..2250')
   if z['local_rot_mats'].shape!=(n,34,3,3) or z['root_positions'].shape!=(n,3) or z['posed_joints'].shape!=(n,34,3):
    raise ValueError('Expected native G1Skeleton34 rotation/root/position shapes')
   if not all(np.isfinite(z[k]).all() for k in ['local_rot_mats','root_positions','posed_joints']):raise ValueError('NaN/Inf input')
   R=z['local_rot_mats']
   if np.max(abs(np.swapaxes(R,-1,-2)@R-np.eye(3)))>1e-4 or np.max(abs(np.linalg.det(R)-1))>1e-4:
    raise ValueError('Nonrotation local matrices')
   summary=json.loads((ROOT/'src/original_motions/summary.json').read_text())
   assert summary['skeleton_cls']=='G1Skeleton34' and len(summary['bone_names'])==34
   self.qpos,self.joint_names=convert(z,summary['bone_names'],ROOT/'src/ardy_converter_g1.xml')
   self.text=str(z['text']);self.fps=fps
  self.times=np.arange(n)/fps
  self.audit=dict(source_npz=str(path),source_npz_sha256=s.sha(path),source_fps=fps,native_frames=n,
                  native_clip_duration_s=n/fps,last_sample_time_s=float(self.times[-1]),
                  expected50Hz_frames=int(np.ceil(self.times[-1]*50-1e-9))+1,
                  converter_sha=s.sha(__file__),vendor_converter_sha=s.sha(ROOT/'official_refs/ardy_mujoco_converter.py'),
                  converter_asset_sha=s.sha(ROOT/'src/ardy_converter_g1.xml'),
                  joint_names=self.joint_names,body_order='MuJoCo XML hinge order; SONIC remaps to IsaacLab explicitly',
                  text=self.text,conversion='native local_rot_mats + root_positions; no angles inferred from posed_joints')
  if check_csv:
   ref=np.loadtxt(check_csv,delimiter=',')
   if ref.shape!=self.qpos.shape:raise ValueError('Paired CSV frame/schema mismatch')
   if not np.isfinite(ref).all():raise ValueError('Paired CSV NaN/Inf input')
   if np.max(abs(np.linalg.norm(ref[:,3:7],axis=1)-1))>1e-5:raise ValueError('Paired CSV non-unit quaternion')
   joint_error=float(np.max(abs(ref[:,7:]-self.qpos[:,7:])))
   pos_error=float(np.max(abs(ref[:,:3]-self.qpos[:,:3])))
   rot_error=max(float(np.max(abs(s.rotation(a)-s.rotation(b)))) for a,b in zip(ref[:,3:7],self.qpos[:,3:7]))
   self.audit.update(paired_csv_sha256=s.sha(check_csv),parity_joint_max_rad=joint_error,
                     parity_root_translation_max_m=pos_error,parity_rotation_matrix_max=rot_error)
   if max(joint_error,pos_error,rot_error)>1e-6:raise ValueError('Vendor CSV parity failed: '+str(self.audit))

 def sample(self,times):
  times=np.asarray(times,dtype=np.float64)
  if times.ndim!=1 or not 1<=len(times)<=10000 or not np.isfinite(times).all():raise ValueError('Sample clock must be finite 1D,1..10000 times')
  x=np.clip(times*self.fps,0,len(self.qpos)-1)
  i=x.astype(int);j=np.minimum(i+1,len(self.qpos)-1);u=x-i
  q=(1-u[:,None])*self.qpos[i,7:]+u[:,None]*self.qpos[j,7:]
  v=(self.qpos[j,7:]-self.qpos[i,7:])*self.fps
  v[times<0]=0
  r=[]
  for a,b,f in zip(self.qpos[i,3:7],self.qpos[j,3:7],u):
   if a@b<0:b=-b
   angle=np.arccos(np.clip(a@b,-1,1))
   z=(1-f)*a+f*b if angle<1e-6 else (np.sin((1-f)*angle)*a+np.sin(f*angle)*b)/np.sin(angle)
   r.append(z/np.linalg.norm(z))
  return q,v,np.asarray(r)

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--out',default='native-npz-contract.json');a=p.parse_args()
 out=ROOT/'out'/a.out
 if out.parent!=ROOT/'out' or out.exists():raise ValueError('Contract output must be a new filename under own out directory')
 reports=[]
 for stem in ['control_s42','near_s42','far_s42']:
  path=ROOT/'src/original_motions'/stem
  motion=ArdyMotion(path.with_suffix('.npz'),check_csv=path.with_suffix('.csv'))
  reports.append(motion.audit)
 out.write_text(json.dumps(reports,indent=2)+'\n')
 print(json.dumps(reports,indent=2))
