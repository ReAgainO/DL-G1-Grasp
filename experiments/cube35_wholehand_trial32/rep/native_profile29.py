"""Native wrist backbone retained; stable stance and contact corridor are projected."""
from pathlib import Path
import numpy as np,json,mujoco
from normal_runner27 import wrist_ik
import sonic_grasp as g,sonic_v11 as s
r=Path(__file__).resolve().parent;o=r/'out/native_profile29';o.mkdir();old=r/'out/native_profile28'
z=np.load(old/'profile.npz');qold=np.array(z['body_q']);qproposal=np.array(z['proposed_body_q']);wpold=np.array(z['wrist_xyz']);Rold=np.array(z['wrist_R']);rootq=np.array(z['root_quat']);bundle=json.loads((r/'out/surface_exec25_plan.json').read_text());way={p['name']:p for p in bundle['waypoints']};plan=bundle['grasp_plan']
m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial27/scene.xml'));d=mujoco.MjData(m);base=np.load(r/'out/normal_trial27/trajectory.npz')['qpos'][0];j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];va=m.jnt_dofadr[j];w=m.body('right_wrist_yaw_link').id;res=[];wps=[];Rs=[];ikerr=[];freeze=[]
for f in range(200):
 q=qold[f].copy();wp=wpold[f].copy();R=Rold[f].copy()
 if f>=125:
  # Recover the native lift horizontal/orientation proposal even where
  # profile28 had replaced the whole body because of an unused-arm collision.
  d.qpos[:]=base;d.qpos[qa[:29]]=qproposal[f];mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);wp=d.xpos[w].copy();R=d.xmat[w].reshape(3,3).copy();u=(f-125)/74;wp[2]=plan['wrist_target'][2]+.1*u**3*(10-15*u+6*u*u)
 if 94<=f<=110:
  u=(f-94)/16;a=u**3*(10-15*u+6*u*u);wp=(1-a)*wpold[94]+a*np.array(way['GRASP']['wrist_p']);R=g.rotation_blend(Rold[94],np.array(way['GRASP']['wrist_R']),a)
 elif 110<f<125:
  u=(f-110)/15;a=u**3*(10-15*u+6*u*u);wp=(1-a)*np.array(way['GRASP']['wrist_p'])+a*np.array(plan['wrist_target']);R=g.rotation_blend(np.array(way['GRASP']['wrist_R']),np.array(plan['wrist_R']),a)
 if f>=60:q[:22]=qold[60,:22];freeze.append(f)
 d.qpos[:]=base;d.qpos[qa[:29]]=q;q[22:29]=wrist_ik(m,d,qa[22:29],va[22:29],w,wp,R,q[22:29]);d.qpos[qa[:29]]=q;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
 ikerr.append(float(np.linalg.norm(d.xpos[w]-wp)));res.append(q.copy());wps.append(d.xpos[w].copy());Rs.append(d.xmat[w].reshape(3,3).copy())
res=np.array(res);np.savez_compressed(o/'profile.npz',body_q=res,proposed_body_q=qproposal,native_body_q=z['native_body_q'],wrist_xyz=wps,wrist_R=Rs,root_quat=rootq,fps=25,anchors=z['anchors'],fallback_frames=z['fallback_frames'],source_native_sha256=z['source_native_sha256'])
stamp=json.loads((old/'manifest.json').read_text());stamp.update(kind='native ARDY decoded body reference with explicit sparse/safety repair; preserve native wrist backbone before contact and native lift XY/rotation; contact corridor94..125; stand/unused-arm constraint60..199',profile_sha256=s.sha(o/'profile.npz'),source_code_sha256=s.sha(__file__),previous_profile_sha256=s.sha(old/'profile.npz'),contact_corridor_frames=[94,125],fixed_other_body_frames=[60,199],reference_ik_max_wrist_error_mm=max(ikerr)*1000,raw_to_final_mean_abs_rad=float(abs(res-z['native_body_q']).mean()),raw_to_final_max_rad=float(abs(res-z['native_body_q']).max()),physical_success=False,active_in_controller=False)
(o/'manifest.json').write_text(json.dumps(stamp,indent=2));print(json.dumps({k:stamp[k] for k in ['profile_sha256','reference_ik_max_wrist_error_mm','raw_to_final_mean_abs_rad','raw_to_final_max_rad']}),flush=True)
