from pathlib import Path
import json,numpy as np,mujoco
from grip_force26 import GripForce26
r=Path(__file__).resolve().parent;o=r/'out/normal_trial25';result=json.loads((o/'result.json').read_text());tr=np.load(o/'trajectory.npz');k=np.flatnonzero(tr['phase']=='TEST_LIFT')[0]
m=mujoco.MjModel.from_xml_path(str(o/'scene.xml'));d=mujoco.MjData(m);d.qpos[:]=tr['qpos'][k];mujoco.mj_forward(m,d);j=m.actuator_trnid[:,0];qa=m.jnt_qposadr[j];va=m.jnt_dofadr[j];q=d.qpos[qa[36:43]].copy();anchors=result['grip_anchor_manifest'];p0=[];ns=[]
for a in anchors:
 gg=a['geom'];R=d.geom_xmat[gg].reshape(3,3);p0.append(d.geom_xpos[gg]+R@np.array(a['local_point']));ns.append(R@np.array(a['local_normal']))
ctrl=GripForce26(m,qa[36:43],va[36:43],anchors,q,0,-1.);new=ctrl.update(d,np.zeros(3));d.qpos[qa[36:43]]=new;mujoco.mj_kinematics(m,d);mujoco.mj_comPos(m,d);closure=[]
for a,p,n in zip(anchors,p0,ns):
 gg=a['geom'];pp=d.geom_xpos[gg]+d.geom_xmat[gg].reshape(3,3)@np.array(a['local_point']);closure.append(float(n@(pp-p)))
assert min(closure)>0,closure
res=dict(actual_kinematic_inward_delta_m=closure,joint_delta_rad=(new-q).tolist(),observer_only_no_physics_step=True,grip_force_audit=ctrl.audit(),stability_or_grasp_success_not_established=True)
(r/'out/grip_force26_static_probe.json').write_text(json.dumps(res,indent=2));print(json.dumps(res),flush=True)
