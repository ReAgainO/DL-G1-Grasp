"""Real physical SONIC pose probe. No body-target overrides, grasp success not evaluated."""
from pathlib import Path
import numpy as np,mujoco,json,time
import sonic_v11 as s,source_physics_core as core
from stable_hand import stable_hand_torques
r=Path(__file__).resolve().parent;o=r/'out/surface_body22';o.mkdir()
m=mujoco.MjModel.from_xml_path(str(r/'out/normal_trial16/scene.xml'));d=mujoco.MjData(m)
tr=np.load(r/'out/normal_trial16/trajectory.npz');d.qpos[:]=tr['qpos'][0];d.qvel[:]=0;mujoco.mj_forward(m,d)
c=s.SonicV11(m);j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];va=m.jnt_dofadr[j];q0=d.qpos[c.aq].copy();lh=d.qpos[qa[29:36]].copy();rh=d.qpos[qa[36:43]].copy();w=m.body('right_wrist_yaw_link').id;cube=m.body('red_cube').id
initial=((q0-s.DEFAULT_ANGLES)/s.ACTION_SCALE)[s.I2M].astype(np.float32);c.last_action=initial.copy()
for k,a in dict(gyro=np.zeros(3),q=q0[s.I2M]-s.DEFAULT_ANGLES[s.I2M],v=np.zeros(29),action=initial,gravity=np.array([0.,0.,-1.])).items():c.hist[k].clear();c.hist[k].extend([a.copy() for _ in range(10)])
route=json.loads((r/'out/surface_route22/route.json').read_text())['approach_route'];target=np.array(route[-1]);safe=np.array(route[1]);lo=m.jnt_range[j[22:29],0]+.006;hi=m.jnt_range[j[22:29],1]-.006
def blend(a,b,t,T):
 u=np.clip(t/T,0,1);z=u*u*u*(10-15*u+6*u*u);dz=(30*u*u-60*u*u*u+30*u*u*u*u)/T if 0<t<T else 0.
 return a+(b-a)*z,(b-a)*dz
def sample(t):
 if t<4:return q0[22:29],np.zeros(7)
 if t<18:return blend(q0[22:29],safe,t-4,12)
 return blend(safe,target,t-18,18)
bias=np.zeros(7);corr=np.zeros(7);kp,kd=core.gains();rows=[];frames=[];refs=[];actions=[];tic=time.monotonic();maxext=0.;maxself=0.;maxtable=0.;maxspeed=0.;warnings0=[x.number for x in d.warning]
rootpos=d.qpos[:3].copy();fk=mujoco.MjData(m);fk.qpos[:]=d.qpos;fk.qpos[qa[22:29]]=target;mujoco.mj_forward(m,fk);targetwp=fk.xpos[w].copy()
for step in range(28000):
 t=d.time
 if step%10==0:
  q,v=sample(t)
  if t>39:bias=np.clip(bias+.02*.12*(target-d.qpos[qa[22:29]]),-.3,.3)
  corr+=np.clip(bias-corr,-.001,.001)
  future=np.tile(q0,(10,1));fv=np.zeros_like(future)
  for k in range(10):
   q,v=sample(t+k*.1);future[k,22:29]=np.clip(q+corr,lo,hi);fv[k,22:29]=v
  c.step_policy(d,future,fv,np.tile([1.,0,0,0],(10,1)))
 d.ctrl[:29]=c.torques(d,1.,1.,2.)
 if t<4:
  u=np.clip(t/4,0,1);alpha=.1+.9*u*u*u*(10-15*u+6*u*u)
  tau=s.KP*(c.target-d.qpos[c.aq])-s.KD*d.qvel[c.av];tau[15:29]-=s.KD[15:29]*d.qvel[c.av[15:29]]
  tau[15:29]-=(1-alpha)*s.KP[15:29]*(c.target[15:29]-d.qpos[c.aq[15:29]])
  d.ctrl[:29]=np.clip(tau,m.actuator_ctrlrange[:29,0],m.actuator_ctrlrange[:29,1])
 # Left/right model-gravity feedforward in actuator adapter only.
 ff=mujoco.MjData(m) if step==0 else ff
 if step%10==0:ff.qpos[:]=d.qpos;ff.qvel[:]=0;mujoco.mj_forward(m,ff);gravity=ff.qfrc_bias[c.av[15:22]].copy()
 d.ctrl[15:22]=np.clip(d.ctrl[15:22]+gravity,m.actuator_ctrlrange[15:22,0],m.actuator_ctrlrange[15:22,1])
 d.ctrl[29:36]=stable_hand_torques(m,d,qa[29:36],va[29:36],lh,kp[core.HAND],kd[core.HAND],m.actuator_ctrlrange[29:36],3.)
 d.ctrl[36:43]=stable_hand_torques(m,d,qa[36:43],va[36:43],rh,kp[core.HAND],kd[core.HAND],m.actuator_ctrlrange[36:43],3.)
 maxext=max(maxext,float(abs(d.xfrc_applied).max()),float(abs(d.qfrc_applied).max()));mujoco.mj_step(m,d)
 for k,ct in enumerate(d.contact[:d.ncon]):
  fn=np.zeros(6);mujoco.mj_contactForce(m,d,k,fn)
  if m.geom('table_top').id in [ct.geom1,ct.geom2] and cube not in [m.geom_bodyid[ct.geom1],m.geom_bodyid[ct.geom2]]:maxtable=max(maxtable,float(fn[0]))
  if m.geom_bodyid[ct.geom1]!=0 and m.geom_bodyid[ct.geom2]!=0 and cube not in [m.geom_bodyid[ct.geom1],m.geom_bodyid[ct.geom2]]:maxself=max(maxself,float(fn[0]))
 maxspeed=max(maxspeed,float(abs(d.qvel[va[15:29]]).max()))
 if step%20==0:
  rows.append([d.time,*d.xpos[w],*d.qpos[qa[22:29]],*c.target[22:29],*corr,float(s.rotation(d.qpos[3:7])[2,2])]);frames.append(d.qpos.copy());refs.append(future[0].copy());actions.append(c.target.copy())
 if step%1000==0:print(json.dumps(dict(t=t,arm_error=float(abs(target-d.qpos[qa[22:29]]).max()),wrist_error_mm=float(np.linalg.norm(targetwp-d.xpos[w])*1000),bias=corr.tolist(),table_N=maxtable)),flush=True)
 if d.qpos[2]<.55 or not np.isfinite(d.qpos).all():break
res=dict(kind='SONIC physical approach pose diagnostic, no grasp success evaluated',body_target_override=False,ardy_active=False,scenario=dict(cube_edge_m=.035,base_x=-.06),final_arm=d.qpos[qa[22:29]].tolist(),goal_arm=target.tolist(),final_wrist=d.xpos[w].tolist(),planned_wrist=targetwp.tolist(),final_arm_error_rad=float(abs(target-d.qpos[qa[22:29]]).max()),final_wrist_error_mm=float(np.linalg.norm(targetwp-d.xpos[w])*1000),max_arm_speed_rad_s=maxspeed,max_robot_table_normal_N=maxtable,max_self_contact_normal_N=maxself,max_external=maxext,reference_bias_rad=corr.tolist(),sonic=c.audit(),wall_s=time.monotonic()-tic,warning_deltas=(np.array([x.number for x in d.warning])-warnings0).tolist())
(o/'result.json').write_text(json.dumps(res,indent=2));np.savez_compressed(o/'trajectory.npz',qpos=frames,body_reference=refs,decoded_targets=actions,telemetry=rows,fps=25);print('RESULT',json.dumps(res),flush=True)
