"""Task stance and a narrow native-residual approach corridor around grasp."""
from pathlib import Path
import json,numpy as np,mujoco
from scipy.spatial.transform import Rotation
from normal_runner27 import wrist_ik
import sonic_grasp as g,sonic_v11 as s
r=Path(__file__).resolve().parent;o=r/'out/native_profile30';o.mkdir();old=r/'out/native_profile29';z=np.load(old/'profile.npz');q=np.array(z['body_q']);wp=np.array(z['wrist_xyz']);R=np.array(z['wrist_R']);bundle=json.loads((r/'out/surface_exec25_plan.json').read_text());way={p['name']:p for p in bundle['waypoints']};plan=bundle['grasp_plan']
m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial27/scene.xml'));d=mujoco.MjData(m);base=np.load(r/'out/normal_trial27/trajectory.npz')['qpos'][0];j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];va=m.jnt_dofadr[j];w=m.body('right_wrist_yaw_link').id
neutral=g.neutral_body(m,s.DEFAULT_ANGLES,0.);neutral[22:29]=way['INITIAL']['arm_q'];neutral[15:22]=neutral[22:29]*np.array([1,-1,-1,1,-1,1,-1])
initial_wp=wp.copy();initial_R=R.copy();errors=[]
for f in range(200):
 if 60<=f<=110:
  u=(f-60)/50;a=u**3*(10-15*u+6*u*u);nom=(1-a)*np.array(way['PRE']['wrist_p'])+a*np.array(way['GRASP']['wrist_p']);res=np.clip(initial_wp[f]-nom,-.005,.005)*np.sin(np.pi*u)**2;wp[f]=nom+res
  nr=g.rotation_blend(np.array(way['PRE']['wrist_R']),np.array(way['GRASP']['wrist_R']),a);v=Rotation.from_matrix(initial_R[f]@nr.T).as_rotvec();v*=min(1.,.05/max(np.linalg.norm(v),1e-12))*np.sin(np.pi*u)**2;R[f]=Rotation.from_rotvec(v).as_matrix()@nr
 q[f,:22]=neutral[:22]
 d.qpos[:]=base;d.qpos[qa[:29]]=q[f];q[f,22:29]=wrist_ik(m,d,qa[22:29],va[22:29],w,wp[f],R[f],q[f,22:29]);d.qpos[qa[:29]]=q[f];mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);errors.append(float(np.linalg.norm(d.xpos[w]-wp[f])));wp[f]=d.xpos[w].copy();R[f]=d.xmat[w].reshape(3,3).copy()
np.savez_compressed(o/'profile.npz',body_q=q,proposed_body_q=z['proposed_body_q'],native_body_q=z['native_body_q'],wrist_xyz=wp,wrist_R=R,root_quat=z['root_quat'],fps=25,anchors=z['anchors'],fallback_frames=z['fallback_frames'],source_native_sha256=z['source_native_sha256'])
stamp=json.loads((old/'manifest.json').read_text());stamp.update(kind='native ARDY wrist backbone with sparse geometry/safety repair; task stationary stance projected allframes; neargrasp60..110 residual-limited corridor5mm/.05rad; actual native paths retained beforehover and inlift',profile_sha256=s.sha(o/'profile.npz'),previous_profile_sha256=s.sha(old/'profile.npz'),source_code_sha256=s.sha(__file__),near_contact_corridor_frames=[60,125],native_residual_position_cap_m=.005,native_residual_rotation_cap_rad=.05,fixed_other_body_frames=[0,199],reference_ik_max_wrist_error_mm=max(errors)*1000,raw_to_final_mean_abs_rad=float(abs(q-z['native_body_q']).mean()),raw_to_final_max_rad=float(abs(q-z['native_body_q']).max()),physical_success=False,active_in_controller=False)
(o/'manifest.json').write_text(json.dumps(stamp,indent=2));print(json.dumps({k:stamp[k] for k in ['reference_ik_max_wrist_error_mm','profile_sha256','raw_to_final_mean_abs_rad']}),flush=True)
