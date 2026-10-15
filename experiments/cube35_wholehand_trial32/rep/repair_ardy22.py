"""Additive sparse-keyframe repair of an attributed native ARDY decoded motion."""
from pathlib import Path
import json,numpy as np,mujoco,xml.etree.ElementTree as ET
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation
from motion_input import ArdyMotion,convert,COORD
import sonic_v11 as s
r=Path(__file__).resolve().parent;o=r/'out/native_ardy22';original=o/'generated_s42.npz';motion=ArdyMotion(original,check_csv=o/'generated_s42.csv');p=json.loads((o/'planned_keyframes.json').read_text())
m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial16/scene.xml'));j=m.actuator_trnid[:29,0];names=[m.joint(i).name for i in j];assert names==motion.joint_names
way=json.loads((r/'out/surface_route22/route.json').read_text())['approach_route'];anchors=[0,30,60,125,199];aq=np.asarray(p['body_joint_q']);safe=aq[0].copy();safe[22:29]=way[1];desired=np.array([aq[0],safe,aq[1],aq[2],aq[3]])
raw=motion.qpos[:,7:].copy();errors=desired-raw[anchors];correction=CubicSpline(np.array(anchors)/25,errors,axis=0,bc_type=((1,np.zeros(29)),(1,np.zeros(29))))(motion.times);qr=raw+correction
lower=m.jnt_range[j,0]+.006;upper=m.jnt_range[j,1]-.006;clipped=np.clip(qr,lower,upper);clipcount=int(np.count_nonzero(clipped!=qr));qr=clipped;assert np.max(abs(qr[anchors]-desired))<1e-10
with np.load(original) as z:arrays={k:np.array(z[k]) for k in z.files}
lr=arrays['local_rot_mats'].copy();xml=r/'src/ardy_converter_g1.xml';tree=ET.parse(xml);defaults={x.get('class'):x.find('joint').get('axis') for x in tree.getroot().findall('.//default') if x.get('class') and x.find('joint') is not None};parents={c:p for p in tree.getroot().iter() for c in p};bone_names=json.loads((r/'src/original_motions/summary.json').read_text())['bone_names'];rootR=s.rotation(np.array(p['root_wxyz'][0]))
lr[:,0]=COORD@rootR@COORD.T
for i,joint in enumerate(tree.getroot().find('worldbody').findall('.//joint')):
 idx=bone_names.index(joint.get('name').replace('_joint','_skel'));axis=np.fromstring(joint.get('axis') or defaults[joint.get('class')],sep=' ');axis=COORD@axis;body=parents[joint];offset=np.eye(3)
 if body.get('quat'):offset=(COORD@s.rotation(np.fromstring(body.get('quat'),sep=' '))@COORD.T).T
 lr[:,idx]=offset.T@Rotation.from_rotvec(qr[:,i,None]*axis[None]).as_matrix()
arrays['local_rot_mats']=lr;arrays['root_positions']=np.tile(np.asarray(p['root_xyz'][0])@COORD.T,(200,1)).astype(np.float32)
# posed_joints is regenerated as a separate native-skeleton FK in the next
# validation step; do not label the current derived container native-generated.
arrays['source_native_sha256']=np.asarray(s.sha(original));arrays['repair_kind']=np.asarray('additive CubicSpline correction through5 explicit planned body keyframes + original joint-limit clamp; root anchored; posed_joints awaiting nativeFK')
out=o/'repaired_s42_pending_fk.npz';np.savez_compressed(out,**arrays)
qcheck,_=convert(arrays,bone_names,xml);err=float(abs(qcheck[:,7:]-qr).max());assert err<2e-6,err
csv=o/'repaired_s42.csv';np.savetxt(csv,qcheck,delimiter=',')
stamp=dict(native_generated=False,source_native_sha256=s.sha(original),source_manifest_sha256=s.sha(o/'generation-manifest.json'),method='Original decoded29 motion plus C2 additive correction interpolating5 exact planned keyframes, including safe raised entry; preserve native residual between anchors; bound originaljointlimits; root fixed to explicitplan',anchors=anchors,anchor_q_max_error_rad=float(abs(qcheck[anchors,7:]-desired).max()),inverse_converter_max_error_rad=err,correction_max_rad=float(abs(correction).max()),correction_mean_abs_rad=float(abs(correction).mean()),joint_clip_cells=clipcount,root_projection_max_m=float(np.max(np.linalg.norm(motion.qpos[:,:3]-np.asarray(p['root_xyz'][0]),axis=1))),source_code_sha256=s.sha(__file__),derived_motion_sha256=s.sha(out),paired_csv_sha256=s.sha(csv),pose_fk_validated=False,physical_success=False,active_in_controller=False)
(o/'repair-manifest-pending.json').write_text(json.dumps(stamp,indent=2));print(json.dumps(stamp),flush=True)
