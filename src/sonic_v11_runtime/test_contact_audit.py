"""Synthetic sign/coverage tests plus a static mj_forward table force check."""
import hashlib,json,sys
from pathlib import Path
import numpy as np,mujoco
from contact_audit import cube_wrench,classify,ContactAudit,fingertip_only_gate

root=Path(__file__).resolve().parent;out=root/'out/contact-audit-tests';out.mkdir()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)

F,M=cube_wrench(np.eye(3),[2,3,4,.1,.2,.3],[0,1,0],np.zeros(3),True)
check('identity_geom2_force',np.allclose(F,[2,3,4]))
check('moment_includes_lever_arm',np.allclose(M,[4.1,.2,-1.7]))
F2,M2=cube_wrench(np.eye(3),[2,3,4,.1,.2,.3],[0,1,0],np.zeros(3),False)
check('geom1_reaction_sign',np.allclose(F2,-F) and np.allclose(M2,-M))
frame=np.array([[0,0,1],[1,0,0],[0,1,0]])
F,_=cube_wrench(frame,[5,2,3,0,0,0],[0,0,0],np.zeros(3),True)
check('contact_frame_rows_to_world',np.allclose(F,[2,3,5]))
names=['world','pelvis','right_wrist_yaw_link','right_hand_pad','table']
check('exact_pad_whitelist',classify(3,3,{3},{4},{1,2,3},names)==0)
check('wrist_is_not_pad',classify(2,2,{3},{4},{1,2,3},names)==1)
check('other_robot_recorded',classify(9,3,{3},{4},{1,2,3},names)==2)
check('support_recorded',classify(4,4,{3},{4},{1,2,3},names)==3)
check('unknown_recorded',classify(10,0,{3},{4},{1,2,3},names)==4)
loads=np.zeros((2,5,4));loads[:,0,0]=.5
check('synthetic_pad_only_gate_passes',fingertip_only_gate(loads))
loads[0,1,0]=.002
check('synthetic_wrist_load_gate_fails',not fingertip_only_gate(loads))
loads[0,1,0]=0.;loads[1,2,0]=.002
check('synthetic_other_robot_load_gate_fails',not fingertip_only_gate(loads))
check('empty_hold_gate_fails',not fingertip_only_gate(np.zeros((0,5,4))))
xml='<mujoco><option timestep=".002"/><worldbody><geom name="floor" type="plane" size="1 1 .1"/><body name="pelvis" pos="0 0 1"><geom name="robot" size=".01"/><body name="right_wrist_yaw_link"><geom name="wrist" size=".01" pos="1 0 0"/></body></body><body name="cube" pos="0 0 .016"><freejoint/><geom name="cube_geom" type="box" size=".0175 .0175 .0175" mass=".02"/></body></worldbody></mujoco>'
(out/'scene.xml').write_text(xml)
m=mujoco.MjModel.from_xml_string(xml);d=mujoco.MjData(m);mujoco.mj_forward(m,d)
check('static_forward_has_cube_contact',d.ncon>0)
cg=m.geom('cube_geom').id;cube=m.body('cube').id
stamp=dict(mujoco_version=mujoco.__version__,sys_executable=sys.executable,python_version=sys.version,dt=.002,model_sha={'scene':sha(out/'scene.xml')},scene_generator_sha=sha(__file__),library_sha={'contact_audit':sha(root/'contact_audit.py')})
before=(d.qpos.copy(),d.qvel.copy(),d.qacc.copy(),d.ctrl.copy(),d.qfrc_applied.copy(),d.xfrc_applied.copy())
audit=ContactAudit(m,cube,cg,[],{m.geom('floor').id},out,stamp)
audit.begin(d,'HOLD',0);vertical=0.
for k,c in enumerate(d.contact):
    if cg in (c.geom1,c.geom2):
        w=np.zeros(6);mujoco.mj_contactForce(m,d,k,w);audit.record(c,k,w)
        vertical+=cube_wrench(c.frame,w,c.pos,d.xipos[cube],c.geom2==cg)[0][2]
audit.end();result=audit.finish(-.1,.1)
check('physical_contact_force_upward',vertical>0.)
check('contact_force_acceleration_consistency',abs(vertical-m.body_mass[cube]*9.81-m.body_mass[cube]*d.qacc[2])<1e-6)
check('recorder_never_mutates_state',all(np.array_equal(a,b) for a,b in zip(before,(d.qpos,d.qvel,d.qacc,d.ctrl,d.qfrc_applied,d.xfrc_applied))))
check('all_contact_rows_recorded',result['raw_contact_rows']==d.ncon)
check('loaded_support_audited',result['hold_steps']['support']['loaded_steps']==1)
check('no_robot_contact_positive',result['fingertip_only_robot_contacts_in_hold'])
check('csv_columns_nonempty',(out/'cube_contacts.csv.gz').stat().st_size>200)
(out/'result.json').write_text(json.dumps(dict(runtime_stamp=stamp,physical_steps=0,checks=checks,upward_force_N=vertical,cube_qacc_z=d.qacc[2],passed=True),indent=2)+'\n')
print(json.dumps(dict(checks=checks,physical_steps=0,upward_force_N=vertical,passed=True),indent=2))
