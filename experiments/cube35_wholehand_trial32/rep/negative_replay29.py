"""Counterfactual open-hand replay: same encoder reference, live SONIC decoder."""
import argparse,json,time,hashlib,gzip
from pathlib import Path
import numpy as np,mujoco
import sonic_v11 as s,sonic_grasp as g,source_physics_core as core,real_hand
from stable_hand import stable_hand_torques
from material_hand27 import MaterialHand22
from contact_audit import ContactAudit
from balance_audit_v2 import BalanceAudit
from execution_monitor_v2 import ExecutionMonitor
def run(name,positive):
 r=Path(__file__).resolve().parent;o=r/'out'/name;o.mkdir();src=r/'out'/positive;pos=json.loads((src/'result.json').read_text());assert pos['success'],'Use a successful positive reference'
 tr=np.load(src/'trajectory.npz');io=np.load(src/'sonic_actual_io.npz');enc=np.array(io['encoder_inputs']);nsteps=int(pos['simulation_steps']);assert len(enc)==(nsteps+9)//10
 m=mujoco.MjModel.from_xml_path(str(src/'scene.xml'));d=mujoco.MjData(m);j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];va=m.jnt_dofadr[j];ctrl=s.SonicV11(m);ctrl.mode_ids.add(0);assert ctrl.model_stamp==pos['runtime']['sonic_weights'];bundle=json.loads((r/'out/surface_exec25_plan.json').read_text());way={x['name']:x for x in bundle['waypoints']}
 neutral=g.neutral_body(m,s.DEFAULT_ANGLES,0.);neutral[22:29]=way['INITIAL']['arm_q'];neutral[15:22]=neutral[22:29]*np.array([1,-1,-1,1,-1,1,-1]);rest=np.array([0,0,-.6,1.3,1.7,1.3,1.7]);d.qpos[:3]=[-.06,0,.788740];d.qpos[3:7]=[1,0,0,0];d.qpos[qa[:29]]=neutral;d.qpos[qa[29:36]]=-rest;d.qpos[qa[36:43]]=rest;mujoco.mj_forward(m,d)
 initial=((neutral-s.DEFAULT_ANGLES)/s.ACTION_SCALE)[s.I2M].astype(np.float32);ctrl.last_action=initial.copy()
 for k,a in dict(gyro=np.zeros(3),q=neutral[s.I2M]-s.DEFAULT_ANGLES[s.I2M],v=np.zeros(29),action=initial,gravity=np.array([0.,0.,-1.])).items():ctrl.hist[k].clear();ctrl.hist[k].extend([a.copy() for _ in range(10)])
 cb=m.body('red_cube').id;cg=m.geom('red_cube_geom').id;w=m.body('right_wrist_yaw_link').id;table=m.geom('table_top').id;floor=m.geom('floor').id;cp0=d.xpos[cb].copy();top=d.geom_xpos[table,2]+m.geom_size[table,2];half=m.geom_size[cg,0];solver=MaterialHand22(m,bundle['grasp_plan']);solver.preferred=np.array(bundle['open_hand_q']);solver.gap=.012;cmd=rest.copy();goal=rest.copy();tablefk=mujoco.MjData(m)
 groups,geoms=real_hand.finger_contacts(m);stamp=dict(kind='matched encoded-reference open-hand ablation; replay encoder inputs, re-evaluate actualSONIC encoder and decoder with live negative proprioception; never replay motor commands',positive=positive,positive_result_sha256=s.sha(src/'result.json'),positive_io_sha256=s.sha(src/'sonic_actual_io.npz'),source_sha256=s.sha(__file__),body_override=False,object_state_writes=False,real_hand=True,scene_sha256=s.sha(src/'scene.xml'),source_positive_ardy=pos.get('ardy_consumption'),source_models=ctrl.model_stamp)
 ca=ContactAudit(m,cb,cg,geoms,{table,floor},o,stamp);ba=BalanceAudit(m,{table,floor},stamp,o);ex=ExecutionMonitor(m,1.4);event=pos['events'];hold0=next(e['time'] for e in event if e['phase']=='HOLD');hold1=next(e['time'] for e in event if e['phase']=='RELEASE');rows=[];qframes=[];phases=[];actualactions=[];maxext=0;warnings0=np.array([x.number for x in d.warning]);tic=time.monotonic();kp,kd=core.gains();cq=m.jnt_qposadr[m.body_jntadr[cb]];fail=None
 try:
  for step in range(nsteps):
   t=d.time;phase=next(e['phase'] for e in event[::-1] if e['time']<=t+1e-10)
   if step%10==0:ctrl._decode(d,enc[step//10][None].astype(np.float32))
   d.ctrl[:29]=ctrl.torques(d,1.,1.,3.5)
   if t<8:
    alpha=.1+.9*(np.clip(t/8,0,1)**3)*(10-15*np.clip(t/8,0,1)+6*np.clip(t/8,0,1)**2);tau=s.KP*(ctrl.target-d.qpos[ctrl.aq])-s.KD*d.qvel[ctrl.av];tau[15:29]-=2.5*s.KD[15:29]*d.qvel[ctrl.av[15:29]];tau[15:29]-=(1-alpha)*s.KP[15:29]*(ctrl.target[15:29]-d.qpos[ctrl.aq[15:29]]);tau[22:29]+=ctrl.last_gravity_arm;d.ctrl[:29]=np.clip(tau,m.actuator_ctrlrange[:29,0],m.actuator_ctrlrange[:29,1])
   d.ctrl[15:22]=np.clip(d.ctrl[15:22]+ctrl.gravity_fk.qfrc_bias[ctrl.av[15:22]],m.actuator_ctrlrange[15:22,0],m.actuator_ctrlrange[15:22,1])
   if phase not in ['SETTLE','RAISE','APPROACH'] and step%100==0:
    x=np.clip(t*25,0,len(tr['qpos'])-1);i=int(x);ii=min(i+1,len(tr['qpos'])-1);u=x-i;ghost=(1-u)*tr['qpos'][i,cq:cq+3]+u*tr['qpos'][ii,cq:cq+3];qR=(1-u)*tr['qpos'][i,cq+3:cq+7]+u*tr['qpos'][ii,cq+3:cq+7];qR/=np.linalg.norm(qR)
    if phase in ['PRESHAPE','ALIGN']:
     # Keep open in an attached virtual cube frame during approach as well.
     ghost=d.xpos[w]+d.xmat[w].reshape(3,3)@(np.array(way['GRASP']['wrist_R']).T@(cp0-np.array(way['GRASP']['wrist_p'])));R=d.xmat[w].reshape(3,3)@np.array(way['GRASP']['wrist_R']).T
    else:R=s.rotation(qR)
    proposed=solver.solve(d,ghost,R,cmd);tablefk.qpos[:]=d.qpos;tablefk.qpos[qa[36:43]]=proposed;mujoco.mj_kinematics(m,tablefk);mujoco.mj_comPos(m,tablefk);mujoco.mj_collision(m,tablefk)
    if not any(table in [c.geom1,c.geom2] and (c.geom1 in geoms or c.geom2 in geoms) and c.dist<0 for c in tablefk.contact[:tablefk.ncon]):goal=proposed
   cmd+=np.clip(goal-cmd,-.001,.001);d.ctrl[36:43]=stable_hand_torques(m,d,qa[36:43],va[36:43],cmd,kp[core.HAND],kd[core.HAND],m.actuator_ctrlrange[36:43],3.);d.ctrl[29:36]=stable_hand_torques(m,d,qa[29:36],va[29:36],-rest,kp[core.HAND],kd[core.HAND],m.actuator_ctrlrange[29:36],3.)
   maxext=max(maxext,float(abs(d.xfrc_applied).max()),float(abs(d.qfrc_applied).max()));mujoco.mj_step(m,d);ex.step(d,phase);ca.begin(d,phase,step);forces=np.zeros(3);support=0.
   for k,c in enumerate(d.contact[:d.ncon]):
    if cg not in [c.geom1,c.geom2]:continue
    other=c.geom2 if c.geom1==cg else c.geom1;f=np.zeros(6);mujoco.mj_contactForce(m,d,k,f);ca.record(c,k,f)
    if other in groups:forces[groups[other]]+=max(0.,f[0])
    if other in [table,floor]:support+=max(0.,f[0])
   ca.end();ba.step(d,phase);rel=d.xmat[w].reshape(3,3).T@(d.xpos[cb]-d.xpos[w]);bottom=d.xpos[cb,2]-half*abs(d.xmat[cb].reshape(3,3)[2]).sum();rows.append([d.time,*d.xpos[cb],*rel,*forces,support,bottom,float(s.rotation(d.qpos[3:7])[2,2])])
   if step%20==0:qframes.append(d.qpos.copy());actualactions.append(ctrl.target.copy());phases.append(phase)
   if step%2500==0:print(json.dumps(dict(t=d.time,phase=phase,cube_lift_mm=(d.xpos[cb,2]-cp0[2])*1000,finger_N=forces.tolist())),flush=True)
 except Exception as exc:fail=repr(exc)
 contact=ca.finish(hold0,hold1);balance=ba.finish(hold0,hold1);execution=ex.finish();a=np.array(rows);mask=(a[:,0]>hold0+.02)&(a[:,0]<=hold1);h=a[mask];lift=a[:,3]-cp0[2];hold_lift=bool(len(h) and lift[mask].min()>=.07);digits=bool(len(h) and (h[:,7:10]>.01).sum(axis=1).min()>=2);nosupport=bool(len(h) and h[:,10].max()<.001);clear=bool(len(h) and h[:,11].min()-top>=.04)
 result=dict(kind=stamp['kind'],positive_reference=stamp,negative_control_pass=fail is None and lift.max()<.01 and not(hold_lift and digits and nosupport and clear),would_pass_same_hold_gates=hold_lift and digits and nosupport and clear,hold_gate_components=dict(hold_7cm=hold_lift,two_real_fingers=digits,no_support=nosupport,clearance_4cm=clear),max_lift_m=float(lift.max()),hold_min_lift_m=float(lift[mask].min()) if len(h) else None,fail_reason=fail,simulation_steps=len(rows),no_external=maxext==0,warning_deltas=(np.array([x.number for x in d.warning])-warnings0).tolist(),sonic=ctrl.audit(),contact_audit=contact,balance=balance,execution=execution,wall_s=time.monotonic()-tic)
 (o/'result.json').write_text(json.dumps(result,indent=2));np.savez_compressed(o/'trajectory.npz',qpos=qframes,decoded_targets=actualactions,phase=phases,telemetry=a,fps=25)
 with gzip.open(o/'telemetry.csv.gz','wt') as f:f.write('time,cube_x,cube_y,cube_z,rel_x,rel_y,rel_z,thumb_N,index_N,middle_N,support_N,bottom_z,upright\n');np.savetxt(f,a,delimiter=',')
 print('RESULT',json.dumps({k:result[k] for k in ['negative_control_pass','would_pass_same_hold_gates','max_lift_m','fail_reason','wall_s']}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--positive',required=True);a=p.parse_args();run(a.name,a.positive)
