"""Attributed native body reference with sparse pose repair and static collision guard."""
from pathlib import Path
import json,numpy as np,mujoco
from scipy.interpolate import CubicSpline
from motion_input import ArdyMotion
from normal_runner27 import wrist_ik
from material_hand27 import MaterialHand22
import sonic_grasp as g,sonic_v11 as s
r=Path(__file__).resolve().parent;o=r/'out/native_profile28';o.mkdir()
rawdir=r/'out/native_ardy22';raw=ArdyMotion(rawdir/'generated_s42.npz',check_csv=rawdir/'generated_s42.csv')
bundle=json.loads((r/'out/surface_exec25_plan.json').read_text());way={w['name']:w for w in bundle['waypoints']};plan=bundle['grasp_plan']
m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial27/scene.xml'));d=mujoco.MjData(m);base=np.load(r/'out/normal_trial27/trajectory.npz')['qpos'][0].copy();j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];va=m.jnt_dofadr[j];arm=qa[22:29];av=va[22:29];q0=base[qa[:29]].copy();w=m.body('right_wrist_yaw_link').id;table=m.geom('table_top').id;cube=m.geom('red_cube_geom').id;cube_body=m.geom_bodyid[cube]
assert raw.joint_names==[m.joint(i).name for i in j[:29]]
anchors=np.array([0,30,60,110,125,199]);names=['INITIAL','SAFE','PRE','GRASP','CLOSED','LIFT'];target=[]
for n in names:
 q=q0.copy();q[22:29]=plan['arm_q'] if n=='CLOSED' else way[n]['arm_q'];target.append(q)
target=np.array(target);native=raw.qpos[:,7:];delta=CubicSpline(anchors/25,target-native[anchors],axis=0,bc_type=((1,np.zeros(29)),(1,np.zeros(29))))(raw.times);candidate=np.clip(native+delta,m.jnt_range[j[:29],0]+.006,m.jnt_range[j[:29],1]-.006);candidate[anchors]=target
robot={m.body('pelvis').id}
for b in range(1,m.nbody):
 if int(m.body_parentid[b]) in robot:robot.add(b)
allowed={m.geom(n).id for n in plan['contact_geoms']};solver=MaterialHand22(m,plan);solver.preferred=np.array(bundle['open_hand_q']);cp=np.array([.28,-.118,.7745]);openR=np.array(way['GRASP']['wrist_R']);openP=np.array(way['GRASP']['wrist_p']);offset=openR.T@(cp-openP)
nominal=[];wps=[];Rs=[];fallback=[];final=[];badpairs=[]
def qpose(q,fq):
 d.qpos[:]=base;d.qpos[qa[:29]]=q;d.qpos[qa[36:43]]=fq;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d)
def bad(frame):
 mujoco.mj_collision(m,d);pairs=[]
 for c in d.contact[:d.ncon]:
  a,b=int(c.geom1),int(c.geom2);ra=int(m.geom_bodyid[a]) in robot;rb=int(m.geom_bodyid[b]) in robot
  if c.dist>=-.00005:continue
  if table in [a,b] and (ra or rb) or ra and rb and c.dist<-.0005 or cube in [a,b] and frame<125 and (a if b==cube else b) not in allowed:pairs.append([m.geom(a).name,m.geom(b).name,float(c.dist)])
 return pairs
for f in range(200):
 ix=min(int(np.searchsorted(anchors,f,side='right')-1),len(anchors)-2);u=(f-anchors[ix])/(anchors[ix+1]-anchors[ix]);z=float(g.core.blend(0.,1.,u));nom=q0.copy();nom[22:29]=(1-z)*target[ix,22:29]+z*target[ix+1,22:29]
 # Nominal waypoint curve is only a safety fallback. Native wrist and whole
 # body pose are retained unless a sampled enabled collision is found.
 qr=candidate[f].copy();hand=base[qa[36:43]].copy() if f<60 else np.array(bundle['open_hand_q']) if f<125 else np.array(plan['hand_q'])
 qpose(qr,hand);wp=d.xpos[w].copy();R=d.xmat[w].reshape(3,3).copy()
 if f>=125:
  wp[2]=float(plan['wrist_target'][2])+.1*(u*u*u*(10-15*u+6*u*u));qr[22:29]=wrist_ik(m,d,arm,av,w,wp,R,qr[22:29])
 qpose(qr,hand)
 if 60<=f<110:
  ghost=d.xpos[w]+d.xmat[w].reshape(3,3)@offset;ghostR=d.xmat[w].reshape(3,3)@openR.T;solver.gap=.012;hand=solver.solve(d,ghost,ghostR,hand);qpose(qr,hand)
 elif 110<=f<125:
  solver.gap=.012*(1-z);hand=solver.solve(d,cp,np.eye(3),hand);qpose(qr,hand)
 pairs=bad(f)
 if pairs:
  # Project unsafe native body sample to a raised/grasp waypoint segment,
  # explicitly record the replacement instead of claiming native safety.
  a=way[names[ix]] if names[ix] in way else dict(wrist_p=plan['wrist_target'],wrist_R=plan['wrist_R'])
  b=way[names[ix+1]] if names[ix+1] in way else dict(wrist_p=plan['wrist_target'],wrist_R=plan['wrist_R'])
  wp=(1-z)*np.array(a['wrist_p'])+z*np.array(b['wrist_p']);R=g.rotation_blend(np.array(a['wrist_R']),np.array(b['wrist_R']),z);qpose(nom,hand);nom[22:29]=wrist_ik(m,d,arm,av,w,wp,R,nom[22:29]);qr=nom.copy();qpose(qr,hand)
  badpairs.append(dict(frame=f,native_pairs=pairs,fallback_pairs=bad(f)));fallback.append(f)
 final.append(qr.copy());wps.append(d.xpos[w].copy());Rs.append(d.xmat[w].reshape(3,3).copy());nominal.append(nom)
final=np.array(final);profile=o/'profile.npz';np.savez_compressed(profile,body_q=final,proposed_body_q=candidate,native_body_q=native,wrist_xyz=wps,wrist_R=Rs,root_quat=np.tile(base[3:7],(200,1)),fps=25,anchors=anchors,fallback_frames=fallback,source_native_sha256=raw.audit['source_npz_sha256'])
stamp=dict(native_generated=False,kind='native ARDY decoded29 + explicit sparse C2 keyframe repair, sampled collision fallback, monotonic lift-height projection; no physical success claim',source_native=raw.audit,source_generation_manifest_sha256=s.sha(rawdir/'generation-manifest.json'),hybrid_trace_sha256=s.sha(rawdir/'hybrid_trace_s42.npz'),source_code_sha256=s.sha(__file__),profile_sha256=s.sha(profile),anchors=anchors.tolist(),fallback_frames=fallback,fallback_count=len(fallback),raw_to_final_mean_abs_rad=float(abs(final-native).mean()),raw_to_final_max_rad=float(abs(final-native).max()),static_bad_pairs=badpairs,physical_success=False,active_in_controller=False)
(o/'manifest.json').write_text(json.dumps(stamp,indent=2));print(json.dumps(stamp),flush=True)
